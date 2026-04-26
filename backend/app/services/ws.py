from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

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
