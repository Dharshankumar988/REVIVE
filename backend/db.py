from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(Path(__file__).with_name(".env"))

logger = logging.getLogger("revive.db")

_SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
_SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
_supabase_client: Client | None = None


def _get_supabase_client() -> Client | None:
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not _SUPABASE_URL or not _SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "Supabase persistence is disabled. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env.",
        )
        return None

    _supabase_client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client


async def save_vital(data: dict[str, Any]) -> int | None:
    """Persist a vital row and return the inserted vital id."""
    client = _get_supabase_client()
    if client is None:
        return None

    payload = {
        "patient_id": data.get("patient_id"),
        "hr": int(data["hr"]),
        "spo2": int(data["spo2"]),
        "movement": int(data["movement"]),
        "status": str(data["status"]),
        "trend": str(data["trend"]),
        "scenario": str(data.get("scenario") or "Normal"),
        "source": str(data.get("source") or "simulator"),
        "ts": (data.get("timestamp") or datetime.now(timezone.utc)).isoformat(),
    }

    def _insert() -> int | None:
        response = client.table("vitals").insert(payload).execute()
        rows = response.data or []
        if not rows:
            return None

        inserted_id = rows[0].get("id")
        return int(inserted_id) if inserted_id is not None else None

    try:
        return await asyncio.to_thread(_insert)
    except Exception:
        logger.exception("Failed to insert row into public.vitals")
        return None


async def save_ai_guidance(
    vital_id: int,
    action: str | None,
    steps: list[str],
) -> int | None:
    """Persist AI guidance linked to a vital row and return its id."""
    client = _get_supabase_client()
    if client is None:
        return None

    payload = {
        "vital_id": int(vital_id),
        "instant_action": action,
        "detailed_steps": steps,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    def _insert() -> int | None:
        response = client.table("ai_guidance").insert(payload).execute()
        rows = response.data or []
        if not rows:
            return None

        inserted_id = rows[0].get("id")
        return int(inserted_id) if inserted_id is not None else None

    try:
        return await asyncio.to_thread(_insert)
    except Exception:
        logger.exception("Failed to insert row into public.ai_guidance")
        return None
