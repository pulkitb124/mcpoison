"""Door B demo (tool-description poisoning): baseline vs attacked, for a scenario.

The agent connects to two servers at once: the benign scenario server plus a
malicious server whose one tool has a poisoned description. The benign server is
clean, so any exfil here can only have come from the poisoned description.

  - BASELINE: the malicious tool has an honest description.
  - ATTACKED: the same tool's description hides the injection.

Run:
    python examples/demo_desc_poison.py [scenario] [model-id] [payload-id]
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
PAYLOAD = sys.argv[3] if len(sys.argv) > 3 else "covert"


def _print(result: TrialResult) -> None:
    label = (
        "BASELINE (clean description)"
        if result.is_baseline
        else f"ATTACKED (payload: {result.payload})"
    )
    print(f"\n===== {label} =====")
    print("tools called    :", result.tools_called)
    print(f"attempted exfil : {result.attempted}")
    print(f"successful exfil: {result.succeeded}")
    print(f"task success    : {result.task_success}")
    print("final answer    :", result.final_text[:240])


async def main() -> None:
    scenario = get_scenario(SCENARIO)
    print(f"scenario: {SCENARIO}   door: description   model: {MODEL}   payload: {PAYLOAD}")
    _print(await run_trial(scenario, door="description", payload=None, model=MODEL))
    _print(await run_trial(scenario, door="description", payload=PAYLOAD, model=MODEL))


if __name__ == "__main__":
    asyncio.run(main())
