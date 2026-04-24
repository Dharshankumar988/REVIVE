import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Literal

Scenario = Literal["Stable", "Gradual Decline", "Sudden Cardiac Event"]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


async def vitals_stream(
    scenario: Scenario = "Stable",
    interval_seconds: float = 1.0,
) -> AsyncIterator[dict[str, int | datetime]]:
    """Yield simulated vitals forever for the selected scenario."""
    hr = 74.0
    spo2 = 98.0
    movement = 8.0
    tick = 0

    while True:
        tick += 1

        if scenario == "Stable":
            hr = _clamp(hr + random.uniform(-2, 2), 64, 92)
            spo2 = _clamp(spo2 + random.uniform(-0.2, 0.2), 96, 100)
            movement = _clamp(movement + random.uniform(-3, 3), 2, 20)

        elif scenario == "Gradual Decline":
            hr = _clamp(hr + random.uniform(0, 1.5), 70, 125)
            spo2 = _clamp(spo2 - random.uniform(0.15, 0.45), 82, 99)
            movement = _clamp(movement + random.uniform(-2, 2), 1, 18)

        elif scenario == "Sudden Cardiac Event":
            if tick < 8:
                hr = _clamp(hr + random.uniform(-2, 2), 65, 95)
                spo2 = _clamp(spo2 + random.uniform(-0.4, 0.2), 95, 100)
                movement = _clamp(movement + random.uniform(-2, 2), 2, 15)
            else:
                hr = _clamp(hr + random.uniform(-18, 25), 35, 170)
                spo2 = _clamp(spo2 - random.uniform(1.5, 4), 72, 98)
                movement = _clamp(movement + random.uniform(-6, 12), 0, 60)

        else:
            raise ValueError(
                f"Unknown scenario '{scenario}'. "
                "Use 'Stable', 'Gradual Decline', or 'Sudden Cardiac Event'."
            )

        yield {
            "hr": int(round(hr)),
            "spo2": int(round(spo2)),
            "movement": int(round(movement)),
            "timestamp": datetime.now(timezone.utc),
        }

        await asyncio.sleep(interval_seconds)
