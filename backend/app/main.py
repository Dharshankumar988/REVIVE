from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import mount_routes
from .core.config import settings
from .schemas.requests import IncomingVital
from .services.processor import process_vital
from .services.runtime import RuntimeState
from .services.simulation import SimulationService

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("revive.backend")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    runtime = RuntimeState()

    async def _ingest(sample: IncomingVital) -> dict[str, object]:
        return await process_vital(sample, runtime)

    simulation = SimulationService(ingest_fn=_ingest)

    app.state.runtime = runtime
    app.state.simulation = simulation

    @app.on_event("startup")
    async def startup() -> None:
        await simulation.start()
        logger.info("Simulation auto-started with scenario: %s", simulation.SCENARIOS[simulation.active_choice])

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await simulation.stop()

    mount_routes(app)
    return app


app = create_app()
