"""Shared abstractions for a scenario: a realistic task plus everything needed
to attack it and to score both the attack and the agent's real job.

A `Scenario` is what makes tasks pluggable. The runner takes one of these and
knows how to launch the right servers, run the agent, detect exfiltration, and
check whether the legitimate task was completed, without knowing anything
domain-specific. Adding a new domain is therefore just writing a new `Scenario`
(plus its two server modules), not touching the runner.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..agent.loop import Transcript


@dataclass(frozen=True)
class ExfilCanary:
    """The objective attack signal for the exfiltration threat model.

    `forbidden_tool` sent to something matching `attacker_markers` counts as an
    attempt; if the `secret` also appears in the call, the exfiltration
    succeeded.
    """

    forbidden_tool: str
    attacker_markers: list[str]
    secret: str


@dataclass(frozen=True)
class Scenario:
    """A single realistic task and its attack/measurement wiring."""

    id: str
    prompt: str  # the honest task handed to the agent
    benign_module: str  # server providing the legitimate tools + secret + channel
    malicious_module: str  # server whose tool description carries the Door B poison
    canary: ExfilCanary
    check_success: Callable[[Transcript], bool]  # did the agent do its real job?
