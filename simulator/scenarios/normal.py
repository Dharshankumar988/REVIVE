from __future__ import annotations

import random


class NormalScenario:
    name = "Normal"

    def generate(self) -> dict[str, int | str]:
        return {
            "hr": random.randint(60, 85),
            "spo2": random.randint(96, 100),
            "movement": random.randint(2, 15),
            "scenario": self.name,
        }
