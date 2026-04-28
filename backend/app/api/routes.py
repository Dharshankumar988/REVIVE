from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

from ..schemas.requests import ChatRequest, IncomingVital, ProcessDataRequest, SimulationScenarioRequest
from ..services.processor import process_chat, process_vital
from ..services.runtime import RuntimeState
from ..services.simulation import SimulationService

router = APIRouter()


def _state(request: Request) -> RuntimeState:
    return request.app.state.runtime


def _simulation(request: Request) -> SimulationService:
    return request.app.state.simulation


@router.get("/")
async def root() -> dict[str, str]:
    return {"status": "REVIVE backend running"}


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/simulation/scenario")
async def get_simulation_scenario(request: Request) -> dict[str, Any]:
    return _simulation(request).get_scenario_info()


@router.post("/api/simulation/scenario")
async def set_simulation_scenario(payload: SimulationScenarioRequest, request: Request) -> dict[str, Any]:
    simulation = _simulation(request)
    try:
        simulation.set_scenario(payload.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "scenario": simulation.active_choice,
        "label": simulation.SCENARIOS[simulation.active_choice],
    }


@router.post("/api/vitals")
async def ingest_vitals(payload: IncomingVital, request: Request) -> dict[str, Any]:
    return await process_vital(payload, _state(request))


@router.get("/api/vitals/latest")
async def latest_vitals(request: Request) -> dict[str, Any]:
    latest_payload = _state(request).latest_broadcast_payload
    if latest_payload is None:
        return {"ok": False, "data": None}

    return {"ok": True, "data": latest_payload}


@router.post("/api/chat")
async def chat(payload: ChatRequest) -> dict[str, Any]:
    message = payload.message.strip()
    reply = await process_chat(message, payload.context or {})
    return {
        "ok": True,
        "reply": reply,
    }


@router.post("/api/process")
async def process_data(payload: ProcessDataRequest) -> dict[str, Any]:
    values = payload.values
    if not values:
        return {"ok": False, "error": "values must contain at least one number"}

    if payload.operation == "average":
        result = sum(values) / len(values)
    elif payload.operation == "sum":
        result = sum(values)
    elif payload.operation == "min":
        result = min(values)
    else:
        result = max(values)

    return {
        "ok": True,
        "operation": payload.operation,
        "count": len(values),
        "result": result,
        "tag": payload.tag,
    }


@router.websocket("/ws/vitals")
async def websocket_vitals(websocket: WebSocket) -> None:
    app = websocket.app
    runtime: RuntimeState = app.state.runtime
    simulation: SimulationService = app.state.simulation

    await runtime.ws_manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if not message.strip():
                continue

            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            if str(payload.get("type", "")).strip().lower() != "set_scenario":
                continue

            next_scenario = payload.get("scenario")
            if next_scenario is None:
                await websocket.send_json({"ok": False, "error": "scenario is required"})
                continue

            try:
                active = simulation.set_scenario(next_scenario)
            except ValueError as exc:
                await websocket.send_json({"ok": False, "error": str(exc)})
                continue

            await websocket.send_json(
                {
                    "ok": True,
                    "type": "scenario_ack",
                    "scenario": active,
                    "label": simulation.SCENARIOS[active],
                }
            )
    except WebSocketDisconnect:
        runtime.ws_manager.disconnect(websocket)
    except Exception:
        runtime.ws_manager.disconnect(websocket)


def mount_routes(app: FastAPI) -> None:
    app.include_router(router)
