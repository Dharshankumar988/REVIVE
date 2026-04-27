import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Literal

Scenario = Literal["Stable", "Gradual Decline", "Sudden Cardiac Event", "Cardiac Arrest"]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


async def vitals_stream(
    scenario: Scenario = "Stable",
    interval_seconds: float = 1.0,
) -> AsyncIterator[dict[str, int | datetime]]:
    """Yield simulated vitals forever for the selected scenario."""
    initial_values: dict[str, tuple[float, float, float]] = {
        "Stable": (74.0, 98.0, 8.0),
        "Gradual Decline": (88.0, 95.0, 7.0),
        "Sudden Cardiac Event": (82.0, 96.0, 10.0),
        "Cardiac Arrest": (48.0, 88.0, 2.0),
    }

    try:
        hr, spo2, movement = initial_values[scenario]
    except KeyError as exc:
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            "Use 'Stable', 'Gradual Decline', 'Sudden Cardiac Event', or 'Cardiac Arrest'."
        ) from exc

    tick = 0

    while True:
        tick += 1

        if scenario == "Stable":
            hr = _clamp(hr + random.uniform(-2, 2), 64, 92)
            spo2 = _clamp(spo2 + random.uniform(-0.2, 0.2), 96, 100)
            movement = _clamp(movement + random.uniform(-3, 3), 2, 20)

        elif scenario == "Gradual Decline":
            hr = _clamp(hr + random.uniform(0.4, 1.8), 75, 132)
            spo2 = _clamp(spo2 - random.uniform(0.3, 0.8), 80, 96)
            movement = _clamp(movement + random.uniform(-2.5, 1.5), 1, 14)

        elif scenario == "Sudden Cardiac Event":
            if tick < 3:
                hr = _clamp(hr + random.uniform(-2, 2), 65, 95)
                spo2 = _clamp(spo2 + random.uniform(-0.4, 0.2), 95, 100)
                movement = _clamp(movement + random.uniform(-2, 2), 2, 15)
            else:
                hr = _clamp(hr + random.uniform(-28, 35), 32, 180)
                spo2 = _clamp(spo2 - random.uniform(2.0, 5.5), 68, 97)
                movement = _clamp(movement + random.uniform(-8, 14), 0, 65)

        elif scenario == "Cardiac Arrest":
            hr = _clamp(hr + random.uniform(-24, 2), 0, 45)
            spo2 = _clamp(spo2 - random.uniform(2.5, 6.5), 35, 88)
            movement = _clamp(movement + random.uniform(-2.5, 0.5), 0, 4)

        yield {
            "hr": int(round(hr)),
            "spo2": int(round(spo2)),
            "movement": int(round(movement)),
            "timestamp": datetime.now(timezone.utc),
        }

        await asyncio.sleep(interval_seconds)
