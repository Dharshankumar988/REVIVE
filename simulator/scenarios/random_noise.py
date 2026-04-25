from __future__ import annotations

import random


class RandomNoiseScenario:
    name = "Random Noise"

    def generate(self) -> dict[str, int | str]:
        hr = random.randint(35, 180)
        spo2 = random.randint(55, 100)
        movement = random.randint(0, 80)

        # Inject occasional abrupt spikes and drops for anomaly testing.
        if random.random() < 0.25:
            hr = random.choice([0, random.randint(150, 220)])
        if random.random() < 0.25:
            spo2 = random.choice([random.randint(35, 65), 100])

        return {
            "hr": hr,
            "spo2": spo2,
            "movement": movement,
            "scenario": self.name,
        }
