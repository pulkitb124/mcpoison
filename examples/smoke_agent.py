"""Phase 1 smoke test: prove the agent loop can use a tool end-to-end.

We give the agent a tiny "employee directory" tool and a question it cannot
answer without calling that tool. A successful run shows the full loop:
model -> tool call -> tool result -> final answer.

Run:
    python examples/smoke_agent.py
"""

from __future__ import annotations

import asyncio

from mcpoison.agent import AnthropicClient, Tool, run_agent

DIRECTORY = {
    "ada lovelace": "ada@example.com",
    "alan turing": "alan@example.com",
    "grace hopper": "grace@example.com",
}


def lookup_email(arguments: dict) -> str:
    name = str(arguments.get("name", "")).strip().lower()
    return DIRECTORY.get(name, f"No directory entry found for {name!r}.")


directory_tool = Tool(
    name="lookup_email",
    description="Look up an employee's email address by their full name.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The employee's full name."}
        },
        "required": ["name"],
    },
    handler=lookup_email,
)


async def main() -> None:
    client = AnthropicClient()  # defaults to the cheap Haiku model
    transcript = await run_agent(
        client=client,
        tools=[directory_tool],
        task="What is Ada Lovelace's email address? Use the directory tool to find it.",
    )

    print("\n=================== SUMMARY ===================")
    print(f"stopped because: {transcript.stopped_reason}")
    print(f"tool calls made: {len(transcript.all_tool_calls())}")
    print(f"final answer: {transcript.final_text}")


if __name__ == "__main__":
    asyncio.run(main())
