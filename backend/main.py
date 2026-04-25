from simulator import vitals_stream
from collections import deque
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_engine import generate_detailed_steps, generate_instant_action
from db import save_ai_guidance, save_vital

RiskStatus = Literal["Normal", "Warning", "Critical"]
TrendLabel = Literal["stable", "declining", "critical"]
HISTORY_WINDOW_SECONDS = 60
ROLLING_BASELINE_SIZE = 8

load_dotenv(Path(__file__).with_name(".env"))
PORT = int(os.getenv("PORT", 8000))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("revive.backend")

app = FastAPI(title="REVIVE Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncomingVital(BaseModel):
    hr: int = Field(ge=0, le=260)
    spo2: int = Field(ge=0, le=100)
    movement: int = Field(ge=0, le=500)
    scenario: str = Field(default="Normal", min_length=1)
    source: str = Field(default="simulator", min_length=1)
    patient_id: str | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        logger.info("WebSocket client connected (%s active)", len(self._clients))

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        logger.info("WebSocket client disconnected (%s active)", len(self._clients))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self._clients:
            return

        stale_clients: list[WebSocket] = []
        for socket in self._clients:
            try:
                await socket.send_json(payload)
            except Exception:
                stale_clients.append(socket)

        for socket in stale_clients:
            self.disconnect(socket)


history: deque[dict[str, int | datetime]] = deque()
history_lock = asyncio.Lock()
ws_manager = ConnectionManager()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "REVIVE backend running"}


def assess_status(hr: int, spo2: int) -> RiskStatus:
    if hr < 50 or hr > 150 or spo2 < 90:
        return "Critical"
    if hr < 60 or hr > 110 or spo2 < 94:
        return "Warning"
    return "Normal"


def _prune_history(
    point_history: deque[dict[str, int | datetime]],
    current_time: datetime,
) -> None:
    while point_history:
        oldest_time = point_history[0]["timestamp"]
        if not isinstance(oldest_time, datetime):
            point_history.popleft()
            continue
        if current_time - oldest_time > timedelta(seconds=HISTORY_WINDOW_SECONDS):
            point_history.popleft()
            continue
        break


def _spo2_drop_over_window(point_history: deque[dict[str, int | datetime]]) -> int | None:
    if len(point_history) < 2:
        return None

    oldest = point_history[0].get("spo2")
    latest = point_history[-1].get("spo2")
    if not isinstance(oldest, int) or not isinstance(latest, int):
        return None

    return oldest - latest


def _is_spo2_decreasing_over_time(point_history: deque[dict[str, int | datetime]]) -> bool:
    if len(point_history) < 4:
        return False

    recent = list(point_history)[-6:]
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


def _detect_sudden_spike(point_history: deque[dict[str, int | datetime]]) -> bool:
    if len(point_history) < 2:
        return False

    previous = point_history[-2]
    current = point_history[-1]

    prev_hr = previous.get("hr")
    prev_spo2 = previous.get("spo2")
    curr_hr = current.get("hr")
    curr_spo2 = current.get("spo2")
    if not all(isinstance(v, int) for v in [prev_hr, prev_spo2, curr_hr, curr_spo2]):
        return False

    hr_delta = abs(curr_hr - prev_hr)
    spo2_delta = abs(curr_spo2 - prev_spo2)
    return hr_delta >= 30 or spo2_delta >= 6


def _detect_rolling_anomaly(point_history: deque[dict[str, int | datetime]]) -> bool:
    if len(point_history) < ROLLING_BASELINE_SIZE + 1:
        return False

    window = list(point_history)[-(ROLLING_BASELINE_SIZE + 1):]
    baseline = window[:-1]
    current = window[-1]

    baseline_hr = [int(point["hr"]) for point in baseline if isinstance(point.get("hr"), int)]
    baseline_spo2 = [int(point["spo2"]) for point in baseline if isinstance(point.get("spo2"), int)]

    current_hr = current.get("hr")
    current_spo2 = current.get("spo2")
    if not baseline_hr or not baseline_spo2:
        return False
    if not isinstance(current_hr, int) or not isinstance(current_spo2, int):
        return False

    avg_hr = sum(baseline_hr) / len(baseline_hr)
    avg_spo2 = sum(baseline_spo2) / len(baseline_spo2)

    hr_shift = abs(current_hr - avg_hr)
    spo2_shift = avg_spo2 - current_spo2
    return hr_shift >= 25 or spo2_shift >= 5


def _classify_trend(
    status: RiskStatus,
    spo2_drop: int | None,
    point_history: deque[dict[str, int | datetime]],
    sudden_spike: bool,
    rolling_anomaly: bool,
) -> TrendLabel:
    if status == "Critical":
        return "critical"
    if sudden_spike or rolling_anomaly:
        return "declining"
    if spo2_drop is not None and spo2_drop >= 5:
        return "declining"
    if _is_spo2_decreasing_over_time(point_history):
        return "declining"
    return "stable"


@app.post("/api/vitals")
async def ingest_vitals(payload: IncomingVital) -> dict[str, Any]:
    current_time = datetime.now(timezone.utc)

    point = {
        "hr": payload.hr,
        "spo2": payload.spo2,
        "movement": payload.movement,
        "timestamp": current_time,
    }

    async with history_lock:
        history.append(point)
        _prune_history(history, current_time)

        status = assess_status(payload.hr, payload.spo2)
        spo2_drop = _spo2_drop_over_window(history)
        sudden_spike = _detect_sudden_spike(history)
        rolling_anomaly = _detect_rolling_anomaly(history)

        if status != "Critical" and spo2_drop is not None and spo2_drop >= 5:
            status = "Warning"
        if status == "Normal" and (sudden_spike or rolling_anomaly):
            status = "Warning"

        trend = _classify_trend(
            status=status,
            spo2_drop=spo2_drop,
            point_history=history,
            sudden_spike=sudden_spike,
            rolling_anomaly=rolling_anomaly,
        )

    ai_input: dict[str, Any] = {
        "hr": payload.hr,
        "spo2": payload.spo2,
        "movement": payload.movement,
        "status": status,
    }

    if status == "Critical":
        instant_action = await generate_instant_action(ai_input)
        detailed_steps = generate_detailed_steps(ai_input)
    else:
        instant_action = None
        detailed_steps = []

    vital_id = await save_vital(
        {
            "patient_id": payload.patient_id,
            "hr": payload.hr,
            "spo2": payload.spo2,
            "movement": payload.movement,
            "status": status,
            "trend": trend,
            "scenario": payload.scenario,
            "source": payload.source or "simulator",
            "timestamp": current_time,
        }
    )

    ai_guidance_id: int | None = None
    if vital_id is not None and (instant_action or detailed_steps):
        ai_guidance_id = await save_ai_guidance(vital_id, instant_action, detailed_steps)

    response_payload: dict[str, Any] = {
        "hr": payload.hr,
        "spo2": payload.spo2,
        "movement": payload.movement,
        "timestamp": current_time.isoformat(),
        "status": status,
        "trend": trend,
        "scenario": payload.scenario,
        "source": payload.source or "simulator",
        "instant_action": instant_action,
        "detailed_steps": detailed_steps,
        "anomaly": {
            "sudden_spike": sudden_spike,
            "rolling_anomaly": rolling_anomaly,
        },
    }

    await ws_manager.broadcast(response_payload)

    logger.info(
        "Ingested vital hr=%s spo2=%s movement=%s status=%s trend=%s scenario=%s",
        payload.hr,
        payload.spo2,
        payload.movement,
        status,
        trend,
        payload.scenario,
    )

    return {
        "ok": True,
        "vital_id": vital_id,
        "ai_guidance_id": ai_guidance_id,
        "data": response_payload,
    }


@app.websocket("/ws/vitals")
async def websocket_vitals(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
async def run_simulation():
    async for vitals in vitals_stream():
        payload = IncomingVital(
            hr=vitals["hr"],
            spo2=vitals["spo2"],
            movement=vitals["movement"],
            scenario=vitals.get("scenario", "Simulated"),
            source="simulator",
            patient_id="demo_user"
        )

        await ingest_vitals(payload)
@app.on_event("startup")
async def start_simulation():
    asyncio.create_task(run_simulation())
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
