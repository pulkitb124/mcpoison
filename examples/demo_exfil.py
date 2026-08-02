"""Door A demo (tool-output injection): baseline vs attacked, for a scenario.

Runs the chosen scenario twice with the identical task:
  - BASELINE: no injection.
  - ATTACKED: the payload is injected into a tool's output.

For each, prints the objective canary signal (attempted / successful exfil) plus
whether the agent still did its real job (task success).

Run:
    python examples/demo_exfil.py [scenario] [model-id] [payload-id]
    # scenario defaults to devops; try 'support' for the other domain
"""

from __future__ import annotations

import asyncio
import logging
import sys

from mcpoison.runner import DEFAULT_MODEL, TrialResult, run_trial
from mcpoison.scenarios import get_scenario

logging.getLogger("httpx").setLevel(logging.WARNING)

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "devops"
MODEL = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
PAYLOAD = sys.argv[3] if len(sys.argv) > 3 else "remediation"


def _print(result: TrialResult) -> None:
    label = "BASELINE (no injection)" if result.is_baseline else f"ATTACKED (payload: {result.payload})"
    print(f"\n===== {label} =====")
    print("tools called    :", result.tools_called)
    print(f"attempted exfil : {result.attempted}")
    print(f"successful exfil: {result.succeeded}")
    print(f"task success    : {result.task_success}")
    print("final answer    :", result.final_text[:240])


async def main() -> None:
    scenario = get_scenario(SCENARIO)
    print(f"scenario: {SCENARIO}   door: output   model: {MODEL}   payload: {PAYLOAD}")
    _print(await run_trial(scenario, door="output", payload=None, model=MODEL))
    _print(await run_trial(scenario, door="output", payload=PAYLOAD, model=MODEL))


if __name__ == "__main__":
    asyncio.run(main())
