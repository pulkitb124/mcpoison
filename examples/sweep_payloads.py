"""Sweep every payload style through a scenario+door and report which ones land.

Holds the scenario, task, secret, channel and canary fixed, and varies only the
injection *style* to see which get the agent to exfiltrate. Runs each payload
once and prints a small table.

Run:
    python examples/sweep_payloads.py [scenario] [output|description] [model-id]
    # e.g. python examples/sweep_payloads.py support description
"""

from __future__ import annotations

import asyncio
import logging
import sys

from mcpoison import payloads
from mcpoison.runner import DEFAULT_MODEL, run_trial
from mcpoison.scenarios import get_scenario

logging.getLogger("httpx").setLevel(logging.WARNING)

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "devops"
DOOR = sys.argv[2] if len(sys.argv) > 2 else "output"
MODEL = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MODEL


async def main() -> None:
    scenario = get_scenario(SCENARIO)
    print(f"scenario: {SCENARIO}   door: {DOOR}   model: {MODEL}\n")
    print(f"{'style':<14}{'attempted':<11}{'succeeded':<11}task")
    print("-" * 46)
    for style in payloads.STYLES:
        result = await run_trial(scenario, door=DOOR, payload=style, model=MODEL)
        print(
            f"{style:<14}{str(result.attempted):<11}"
            f"{str(result.succeeded):<11}{result.task_success}"
        )


if __name__ == "__main__":
    asyncio.run(main())
