"""Model client layer.

`ModelClient` is the provider-agnostic interface the agent loop talks to. Each
concrete client (starting with Anthropic) translates our neutral message types
into that provider's tool-calling wire format and parses the response back.

Adding OpenAI/Gemini later means implementing this same interface — the agent
loop never changes, which keeps cross-model comparisons fair.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import anthropic

from ..config import get_key
from .tools import Tool
from .types import AssistantTurn, Message, ToolCall


class ModelClient(ABC):
    provider: str

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def generate(
        self,
        system: str | None,
        messages: list[Message],
        tools: list[Tool],
    ) -> AssistantTurn:
        """Produce the next assistant turn given the conversation and tools."""


class AnthropicClient(ModelClient):
    provider = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5-20251001", max_tokens: int = 1024):
        super().__init__(model)
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=get_key("anthropic"))

    def generate(
        self,
        system: str | None,
        messages: list[Message],
        tools: list[Tool],
    ) -> AssistantTurn:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [self._to_anthropic(m) for m in messages],
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [self._tool_schema(t) for t in tools]

        resp = self._client.messages.create(**kwargs)
        return self._parse(resp)

    @staticmethod
    def _tool_schema(tool: Tool) -> dict:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    @staticmethod
    def _to_anthropic(message: Message) -> dict:
        if message.role == "user":
            return {"role": "user", "content": message.text or ""}

        if message.role == "assistant":
            blocks: list[dict] = []
            if message.text:
                blocks.append({"type": "text", "text": message.text})
            for call in message.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )
            return {"role": "assistant", "content": blocks}

        if message.role == "tool":
            # Anthropic delivers tool results inside a user-role message.
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": result.tool_call_id,
                        "content": result.content,
                    }
                    for result in message.tool_results
                ],
            }

        raise ValueError(f"Unknown message role: {message.role!r}")

    @staticmethod
    def _parse(resp) -> AssistantTurn:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )
        text = "\n".join(text_parts) if text_parts else None
        return AssistantTurn(text=text, tool_calls=tool_calls)
