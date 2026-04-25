from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import error, request

logger = logging.getLogger("revive.simulator.sender")


class VitalsSender:
    def __init__(self, endpoint_url: str, timeout_seconds: float = 3.0) -> None:
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds

    async def send(self, payload: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self._send_sync, payload)

    def _send_sync(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint_url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                ok = 200 <= status < 300
                if not ok:
                    logger.error("[SIM] Non-success status from backend: %s", status)
                return ok
        except error.HTTPError as exc:
            logger.error("[SIM] Backend rejected vital sample: %s %s", exc.code, exc.reason)
            return False
        except error.URLError as exc:
            logger.error("[SIM] Backend unavailable: %s", exc.reason)
            return False
        except TimeoutError:
            logger.error("[SIM] Request timed out while sending vital sample")
            return False
