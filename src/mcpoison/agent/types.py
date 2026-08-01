"""Provider-neutral message types.

Every provider (Anthropic, OpenAI, Gemini) has its own wire format for tool
calling. To keep the agent loop fair and provider-agnostic, we represent a
conversation with these neutral types and let each provider client translate
to/from its own format.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A request from the model to run a tool."""

    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """The result of running a tool, fed back to the model."""

    tool_call_id: str
    content: str


@dataclass
class Message:
    """One turn in the conversation.

    A "tool" message carries results back to the model; an "assistant" message
    may contain text, tool calls, or both.
    """

    role: str  # "user" | "assistant" | "tool"
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)

    @classmethod
    def user(cls, text: str) -> Message:
        return cls(role="user", text=text)

    @classmethod
    def assistant(cls, text: str | None = None, tool_calls: list[ToolCall] | None = None) -> Message:
        return cls(role="assistant", text=text, tool_calls=tool_calls or [])

    @classmethod
    def tool(cls, results: list[ToolResult]) -> Message:
        return cls(role="tool", tool_results=results)


@dataclass
class AssistantTurn:
    """What the model produced in a single generation step."""

    text: str | None
    tool_calls: list[ToolCall]

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)
