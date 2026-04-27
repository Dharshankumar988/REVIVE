from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Awaitable, Callable

from simulator import vitals_stream

from ..schemas.requests import IncomingVital


class SimulationService:
    SCENARIOS: dict[str, str] = {
        "1": "Stable",
        "2": "Gradual Decline",
        "3": "Sudden Cardiac Event",
        "4": "Cardiac Arrest",
    }

    _LABEL_TO_CHOICE: dict[str, str] = {
        "stable": "1",
        "gradual_decline": "2",
        "sudden_cardiac_event": "3",
        "cardiac_arrest": "4",
    }

    def __init__(self, ingest_fn: Callable[[IncomingVital], Awaitable[dict[str, Any]]]) -> None:
        self._ingest_fn = ingest_fn
        self.active_choice = "1"
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="revive-simulation-loop")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return

        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def set_scenario(self, scenario: str) -> str:
        normalized = scenario.strip()
        if normalized in self.SCENARIOS:
            self.active_choice = normalized
            return self.active_choice

        label_key = normalized.lower().replace(" ", "_")
        mapped_choice = self._LABEL_TO_CHOICE.get(label_key)
        if mapped_choice is not None:
            self.active_choice = mapped_choice
            return self.active_choice

        valid_values = ", ".join(sorted(self.SCENARIOS.keys()))
        valid_labels = ", ".join(self.SCENARIOS.values())
        raise ValueError(
            f"Unknown scenario '{scenario}'. Use one of [{valid_values}] "
            f"or labels [{valid_labels}]."
        )

    def get_scenario_info(self) -> dict[str, Any]:
        return {
            "ok": True,
            "scenario": self.active_choice,
            "label": self.SCENARIOS[self.active_choice],
            "options": [{"value": key, "label": label} for key, label in self.SCENARIOS.items()],
        }

    async def _run_loop(self) -> None:
        active_stream_label: str | None = None
        stream = None

        while not self._stop_event.is_set():
            scenario_label = self.SCENARIOS.get(self.active_choice, "Stable")
            if scenario_label != active_stream_label or stream is None:
                active_stream_label = scenario_label
                stream = vitals_stream(scenario=scenario_label)

            try:
                sample = await stream.__anext__()
            except StopAsyncIteration:
                stream = vitals_stream(scenario=scenario_label)
                continue

            await self._ingest_fn(
                IncomingVital(
                    hr=int(sample["hr"]),
                    spo2=int(sample["spo2"]),
                    movement=int(sample["movement"]),
                    scenario=scenario_label,
                    source="simulator",
                )
            )
