from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_engine import generate_chat_reply, generate_detailed_steps, generate_instant_action, generate_veteran_brief
from db import save_ai_guidance, save_vital

from ..schemas.requests import IncomingVital
from .monitoring import (
    assess_status,
    classify_trend,
    detect_rolling_anomaly,
    detect_sudden_spike,
    prune_history,
    spo2_drop_over_window,
)
from .runtime import RuntimeState


async def process_vital(payload: IncomingVital, state: RuntimeState) -> dict[str, Any]:
    current_time = datetime.now(timezone.utc)

    point = {
        "hr": payload.hr,
        "spo2": payload.spo2,
        "movement": payload.movement,
        "timestamp": current_time,
    }

    async with state.history_lock:
        state.history.append(point)
        prune_history(state.history, current_time)

        status = assess_status(payload.hr, payload.spo2)
        spo2_drop = spo2_drop_over_window(state.history)
        sudden_spike = detect_sudden_spike(state.history)
        rolling_anomaly = detect_rolling_anomaly(state.history)

        if status != "Critical" and spo2_drop is not None and spo2_drop >= 5:
            status = "Warning"
        if status == "Normal" and (sudden_spike or rolling_anomaly):
            status = "Warning"

        trend = classify_trend(
            status=status,
            spo2_drop=spo2_drop,
            point_history=state.history,
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
        veteran_brief = await generate_veteran_brief(ai_input)
    else:
        instant_action = None
        detailed_steps = []
        veteran_brief = None

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
        "veteran_brief": veteran_brief,
        "anomaly": {
            "sudden_spike": sudden_spike,
            "rolling_anomaly": rolling_anomaly,
        },
    }

    state.latest_broadcast_payload = response_payload
    await state.ws_manager.broadcast(response_payload)

    return {
        "ok": True,
        "vital_id": vital_id,
        "ai_guidance_id": ai_guidance_id,
        "data": response_payload,
    }


async def process_chat(message: str, context: dict[str, Any] | None = None) -> str:
    return await generate_chat_reply(message.strip(), context or {})
