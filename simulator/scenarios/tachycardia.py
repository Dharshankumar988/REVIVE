from __future__ import annotations

import random


class TachycardiaScenario:
    name = "Tachycardia"

    def generate(self) -> dict[str, int | str]:
        return {
            "hr": random.randint(110, 140),
            "spo2": random.randint(91, 96),
            "movement": random.randint(8, 28),
            "scenario": self.name,
        }
