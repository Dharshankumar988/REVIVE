from __future__ import annotations

import random


class HypoxiaScenario:
    name = "Hypoxia"

    def generate(self) -> dict[str, int | str]:
        return {
            "hr": random.randint(98, 130),
            "spo2": random.randint(70, 88),
            "movement": random.randint(4, 22),
            "scenario": self.name,
        }
