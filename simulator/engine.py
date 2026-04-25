from __future__ import annotations

import asyncio
import logging
from typing import Protocol

try:
    from .sender import VitalsSender
    from .scenarios.cardiac_arrest import CardiacArrestScenario
    from .scenarios.hypoxia import HypoxiaScenario
    from .scenarios.normal import NormalScenario
    from .scenarios.random_noise import RandomNoiseScenario
    from .scenarios.tachycardia import TachycardiaScenario
except ImportError:  # pragma: no cover - direct script fallback
    from sender import VitalsSender
    from scenarios.cardiac_arrest import CardiacArrestScenario
    from scenarios.hypoxia import HypoxiaScenario
    from scenarios.normal import NormalScenario
    from scenarios.random_noise import RandomNoiseScenario
    from scenarios.tachycardia import TachycardiaScenario

logger = logging.getLogger("revive.simulator.engine")


class ScenarioProtocol(Protocol):
    name: str

    def generate(self) -> dict[str, int | str]:
        ...


class SimulationEngine:
    def __init__(self, sender: VitalsSender, interval_seconds: float = 1.0) -> None:
        self.sender = sender
        self.interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

        self._scenarios: dict[str, ScenarioProtocol] = {
            "normal": NormalScenario(),
            "tachycardia": TachycardiaScenario(),
            "hypoxia": HypoxiaScenario(),
            "cardiac_arrest": CardiacArrestScenario(),
            "random_noise": RandomNoiseScenario(),
        }
        self._active_key = "normal"

    @property
    def active_scenario_name(self) -> str:
        return self._scenarios[self._active_key].name

    @property
    def available_scenarios(self) -> dict[str, str]:
        return {key: scenario.name for key, scenario in self._scenarios.items()}

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            logger.info("[SIM] Engine already running")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="simulation-loop")
        logger.info("[SIM] Engine started with scenario: %s", self.active_scenario_name)

    async def stop(self) -> None:
        if self._task is None:
            return

        self._stop_event.set()
        try:
            await self._task
        finally:
            self._task = None
            logger.info("[SIM] Engine stopped")

    def set_scenario(self, scenario_key: str) -> None:
        normalized = scenario_key.strip().lower().replace(" ", "_")
        if normalized not in self._scenarios:
            raise ValueError(f"Unknown scenario '{scenario_key}'")

        self._active_key = normalized
        logger.info("[SIM] Switching to %s", self.active_scenario_name)

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            scenario = self._scenarios[self._active_key]
            sample = scenario.generate()
            sample["source"] = "simulator"

            sent = await self.sender.send(sample)
            if sent:
                logger.info(
                    "[SIM] sent hr=%s spo2=%s movement=%s scenario=%s",
                    sample["hr"],
                    sample["spo2"],
                    sample["movement"],
                    sample["scenario"],
                )

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
