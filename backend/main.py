from collections import deque
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from ai_engine import generate_detailed_steps, generate_instant_action
from simulator import Scenario, vitals_stream

RiskStatus = Literal["Normal", "Warning", "Critical"]
TrendLabel = Literal["stable", "declining", "critical"]
HISTORY_WINDOW_SECONDS = 60

load_dotenv(Path(__file__).with_name(".env"))
PORT = int(os.getenv("PORT", 8080))

app = FastAPI(title="REVIVE Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "REVIVE backend running"}


def assess_status(hr: int, spo2: int) -> RiskStatus:
    if hr < 50 or spo2 < 90:
        return "Critical"
    if hr < 60 or spo2 < 94:
        return "Warning"
    return "Normal"


def _prune_history(
    history: deque[dict[str, int | datetime]],
    current_time: datetime,
) -> None:
    while history:
        oldest_time = history[0]["timestamp"]
        if not isinstance(oldest_time, datetime):
            history.popleft()
            continue
        if current_time - oldest_time > timedelta(seconds=HISTORY_WINDOW_SECONDS):
            history.popleft()
            continue
        break


def _spo2_drop_over_window(history: deque[dict[str, int | datetime]]) -> int | None:
    if len(history) < 2:
        return None

    oldest = history[0].get("spo2")
    latest = history[-1].get("spo2")
    if not isinstance(oldest, int) or not isinstance(latest, int):
        return None

    return oldest - latest


def _is_spo2_decreasing_over_time(history: deque[dict[str, int | datetime]]) -> bool:
    if len(history) < 4:
        return False

    recent = list(history)[-6:]
    spo2_values: list[int] = [
        value
        for point in recent
        if isinstance((value := point.get("spo2")), int)
    ]

    if len(spo2_values) < 4:
        return False

    non_increasing = all(
        next_value <= current_value
        for current_value, next_value in zip(spo2_values, spo2_values[1:])
    )
    return non_increasing and spo2_values[-1] < spo2_values[0]


def _classify_trend(
    status: RiskStatus,
    spo2_drop: int | None,
    history: deque[dict[str, int | datetime]],
) -> TrendLabel:
    if status == "Critical":
        return "critical"
    if spo2_drop is not None and spo2_drop >= 5:
        return "declining"
    if _is_spo2_decreasing_over_time(history):
        return "declining"
    return "stable"


@app.websocket("/ws/vitals")
async def websocket_vitals(websocket: WebSocket) -> None:
    await websocket.accept()

    raw_scenario = websocket.query_params.get("scenario", "Stable")
    scenario: Scenario = raw_scenario if raw_scenario in {
        "Stable",
        "Gradual Decline",
        "Sudden Cardiac Event",
    } else "Stable"
    history: deque[dict[str, int | datetime]] = deque()

    try:
        async for sample in vitals_stream(scenario=scenario):
            timestamp = sample["timestamp"]
            if isinstance(timestamp, datetime):
                current_time = timestamp
                ts_value = timestamp.isoformat()
            else:
                current_time = datetime.now(timezone.utc)
                ts_value = str(timestamp)

            history.append(
                {
                    "hr": sample["hr"],
                    "spo2": sample["spo2"],
                    "movement": sample["movement"],
                    "timestamp": current_time,
                }
            )
            _prune_history(history, current_time)

            status = assess_status(sample["hr"], sample["spo2"])
            spo2_drop = _spo2_drop_over_window(history)
            if status != "Critical" and spo2_drop is not None and spo2_drop >= 5:
                status = "Warning"

            trend = _classify_trend(status, spo2_drop, history)
            vitals: dict[str, Any] = {
                "hr": sample["hr"],
                "spo2": sample["spo2"],
                "movement": sample["movement"],
                "status": status,
            }

            if status == "Critical":
                instant_action = await generate_instant_action(vitals)
                detailed_steps = generate_detailed_steps(vitals)
            else:
                instant_action = None
                detailed_steps = []

            payload = {
                "hr": sample["hr"],
                "spo2": sample["spo2"],
                "movement": sample["movement"],
                "timestamp": ts_value,
                "status": status,
                "scenario": scenario,
                "instant_action": instant_action,
                "detailed_steps": detailed_steps,
                "trend": trend,
            }
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        return
    except Exception:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
