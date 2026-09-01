"""The trial orchestrator.

`run_trial` is the single place that knows how to turn a `Scenario` + a choice
of attack condition into a scored result. It plays the experiment-orchestrator
role: it configures and launches the environment, drives the (oblivious) agent,
then scores both the attack (via the canary) and the real job (via the
scenario's success checker). Nothing about the attack condition is visible to
the agent, only to the runner.

Conditions:
  door="output"       Door A: the payload rides in a tool's output. Baseline is
                      the same server with no injection.
  door="description"  Door B: the payload hides in the malicious server's tool
                      description, alongside the clean benign server. Baseline is
                      the same pair with an honest description.
  payload=None        no attack (the baseline for whichever door).
  defense=NONE        no mitigation (Phase 4). Any other `Defense` rewrites the
                      tool data and/or system prompt the (still-oblivious) agent
                      sees; see defenses.py.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass

from . import canary
from .agent import AnthropicClient, run_agent
from .agent.mcp_client import MCPConnection
from .defenses import NONE, Defense
from .scenarios.base import Scenario

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class TrialResult:
    scenario_id: str
    door: str
    payload: str | None
    defense: str
    attempted: bool
    succeeded: bool
    task_success: bool
    tools_called: list[str]
    final_text: str

    @property
    def is_baseline(self) -> bool:
        return self.payload is None


async def run_trial(
    scenario: Scenario,
    *,
    door: str,
    payload: str | None = None,
    model: str = DEFAULT_MODEL,
    defense: Defense = NONE,
) -> TrialResult:
    async with AsyncExitStack() as stack:
        tools = await _connect(stack, scenario, door, payload)
        tools = defense.apply_to_tools(tools)
        transcript = await run_agent(
            AnthropicClient(model=model),
            tools,
            scenario.prompt,
            system=defense.system,
            output_filter=defense.output_filter(),
            verbose=False,
        )

    report = canary.evaluate_exfiltration(
        transcript,
        forbidden_tool=scenario.canary.forbidden_tool,
        attacker_markers=scenario.canary.attacker_markers,
        secret=scenario.canary.secret,
    )
    return TrialResult(
        scenario_id=scenario.id,
        door=door,
        payload=payload,
        defense=defense.id,
        attempted=report.attempted,
        succeeded=report.succeeded,
        task_success=scenario.check_success(transcript),
        tools_called=[c.name for c in transcript.all_tool_calls()],
        final_text=(transcript.final_text or "").strip(),
    )


async def _connect(stack, scenario: Scenario, door: str, payload: str | None):
    """Launch the right server(s) for the condition and return their tools."""
    if door == "output":
        args = ["--inject", "--payload", payload] if payload else []
        benign = await stack.enter_async_context(
            MCPConnection.for_module(scenario.benign_module, module_args=args)
        )
        return benign.tools

    if door == "description":
        evil_args = ["--poison", "--payload", payload] if payload else []
        benign = await stack.enter_async_context(
            MCPConnection.for_module(scenario.benign_module)
        )
        evil = await stack.enter_async_context(
            MCPConnection.for_module(scenario.malicious_module, module_args=evil_args)
        )
        return benign.tools + evil.tools

    raise ValueError(f"unknown door {door!r}; expected 'output' or 'description'")
