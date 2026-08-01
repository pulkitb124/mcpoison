"""The agent loop.

This is the engine that turns a raw model into a tool-using agent:

    think  ->  request tool(s)  ->  run them  ->  feed results back  ->  repeat

It stops when the model returns a plain text answer (no tool calls) or when it
hits a safety cap on steps. Every step is recorded in a `Transcript` so we can
inspect and, later, measure what happened (e.g. whether a forbidden action fired).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ModelClient
from .tools import Tool
from .types import AssistantTurn, Message, ToolResult


@dataclass
class Step:
    index: int
    turn: AssistantTurn
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class Transcript:
    task: str
    steps: list[Step] = field(default_factory=list)
    final_text: str | None = None
    stopped_reason: str = ""  # "final" | "max_steps"

    def all_tool_calls(self):
        return [call for step in self.steps for call in step.turn.tool_calls]


def run_agent(
    client: ModelClient,
    tools: list[Tool],
    task: str,
    system: str | None = None,
    max_steps: int = 10,
    verbose: bool = True,
) -> Transcript:
    registry = {tool.name: tool for tool in tools}
    messages: list[Message] = [Message.user(task)]
    transcript = Transcript(task=task)

    for i in range(max_steps):
        turn = client.generate(system, messages, tools)
        messages.append(Message.assistant(text=turn.text, tool_calls=turn.tool_calls))
        step = Step(index=i, turn=turn)

        if verbose:
            _print_turn(i, turn)

        if not turn.wants_tools:
            transcript.final_text = turn.text
            transcript.stopped_reason = "final"
            transcript.steps.append(step)
            return transcript

        results: list[ToolResult] = []
        for call in turn.tool_calls:
            tool = registry.get(call.name)
            if tool is None:
                content = f"Error: no tool named {call.name!r} is available."
            else:
                try:
                    content = tool.run(call.arguments)
                except Exception as exc:  # a broken tool shouldn't crash the run
                    content = f"Error running tool {call.name!r}: {exc}"
            results.append(ToolResult(tool_call_id=call.id, content=content))
            if verbose:
                _print_tool_result(call.name, call.arguments, content)

        step.tool_results = results
        transcript.steps.append(step)
        messages.append(Message.tool(results))

    transcript.stopped_reason = "max_steps"
    return transcript


def _print_turn(index: int, turn: AssistantTurn) -> None:
    print(f"\n--- step {index} ---")
    if turn.text:
        print(f"[model] {turn.text}")
    for call in turn.tool_calls:
        print(f"[tool call] {call.name}({call.arguments})")


def _print_tool_result(name: str, arguments: dict, content: str) -> None:
    print(f"[tool result] {name} -> {content}")
