from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    APP_NAME = os.getenv("APP_NAME", "REVIVE Backend API")
    APP_ENV = os.getenv("APP_ENV", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    PORT = int(os.getenv("PORT", "8080"))

    _cors_origins_raw = os.getenv("CORS_ORIGINS", "*").strip()
    CORS_ORIGINS = (
        ["*"]
        if _cors_origins_raw == "*"
        else [origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()]
    )

    SIMULATION_INTERVAL_SECONDS = float(os.getenv("SIMULATION_INTERVAL_SECONDS", "1.0"))


settings = Settings()
