from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urlparse, urlunparse
from urllib import error, request

logger = logging.getLogger("revive.simulator.sender")


class VitalsSender:
    def __init__(self, endpoint_url: str, timeout_seconds: float = 3.0) -> None:
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds

    async def send(self, payload: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self._send_sync, payload)

    def _candidate_endpoints(self) -> list[str]:
        candidates = [self.endpoint_url]

        try:
            parsed = urlparse(self.endpoint_url)
        except Exception:
            return candidates

        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            return candidates

        current_port = parsed.port
        alternate_port = None
        if current_port == 8000:
            alternate_port = 8080
        elif current_port == 8080:
            alternate_port = 8000

        if alternate_port is None:
            return candidates

        host = parsed.hostname or "localhost"
        netloc = f"{host}:{alternate_port}"
        alternate = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        if alternate not in candidates:
            candidates.append(alternate)

        return candidates

    def _send_sync(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload).encode("utf-8")
        last_reason: str | None = None

        for endpoint in self._candidate_endpoints():
            req = request.Request(
                endpoint,
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
                        return False

                    if endpoint != self.endpoint_url:
                        logger.info("[SIM] Backend detected on fallback endpoint %s", endpoint)
                        self.endpoint_url = endpoint
                    return True
            except error.HTTPError as exc:
                logger.error("[SIM] Backend rejected vital sample: %s %s", exc.code, exc.reason)
                return False
            except error.URLError as exc:
                last_reason = str(exc.reason)
            except TimeoutError:
                last_reason = "timeout"

        if last_reason == "timeout":
            logger.error("[SIM] Request timed out while sending vital sample")
            return False

        logger.error("[SIM] Backend unavailable: %s", last_reason if last_reason else "unknown endpoint error")
        return False
