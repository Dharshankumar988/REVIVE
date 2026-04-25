from __future__ import annotations

import argparse
import asyncio
import logging

try:
    from .engine import SimulationEngine
    from .sender import VitalsSender
except ImportError:  # pragma: no cover - direct script fallback
    from engine import SimulationEngine
    from sender import VitalsSender

MENU = """
========= REVIVE Simulation Controller =========
1 - Normal
2 - Tachycardia
3 - Hypoxia
4 - Cardiac Arrest
5 - Random
s - Start engine
x - Stop engine
q - Quit
===============================================
""".strip()

SCENARIO_CHOICES = {
    "1": "normal",
    "2": "tachycardia",
    "3": "hypoxia",
    "4": "cardiac_arrest",
    "5": "random_noise",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="REVIVE standalone vitals simulator")
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000/api/vitals",
        help="Backend ingestion endpoint URL",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between vital samples",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return parser.parse_args()


async def _read_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def run_cli() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    sender = VitalsSender(endpoint_url=args.endpoint)
    engine = SimulationEngine(sender=sender, interval_seconds=args.interval)

    await engine.start()
    print(MENU)

    while True:
        choice = (await _read_input("[SIM] Enter option: ")).strip().lower()

        if choice in SCENARIO_CHOICES:
            key = SCENARIO_CHOICES[choice]
            engine.set_scenario(key)
            print(f"[SIM] Switching to {engine.active_scenario_name}")
            continue

        if choice == "s":
            await engine.start()
            continue

        if choice == "x":
            await engine.stop()
            continue

        if choice == "q":
            await engine.stop()
            print("[SIM] Shutdown complete")
            return

        print("[SIM] Unknown option. Choose 1-5, s, x, or q.")


def main() -> None:
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        print("\n[SIM] Interrupted by user")


if __name__ == "__main__":
    main()
