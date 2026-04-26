from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .ws import ConnectionManager


@dataclass
class RuntimeState:
    history: deque[dict[str, int | datetime]] = field(default_factory=deque)
    history_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ws_manager: ConnectionManager = field(default_factory=ConnectionManager)
    latest_broadcast_payload: dict[str, Any] | None = None
