from __future__ import annotations

import random


class CardiacArrestScenario:
    name = "Cardiac Arrest"

    def generate(self) -> dict[str, int | str]:
        return {
            "hr": 0,
            "spo2": random.randint(40, 72),
            "movement": random.randint(0, 2),
            "scenario": self.name,
        }
