"""Phase 1 (step 6) smoke test: the agent using tools over *real* MCP.

Unlike smoke_agent.py (where the tool was an in-process Python function), here
the tools come from a separate MCP server process. The agent discovers them by
asking the server for its tool list, and every tool call travels over the MCP
protocol.

Run:
    python examples/smoke_mcp.py
"""

from __future__ import annotations

import asyncio

from mcpoison.agent import AnthropicClient, run_agent
from mcpoison.agent.mcp_client import MCPConnection


async def main() -> None:
    async with MCPConnection.for_module("mcpoison.servers.benign") as conn:
        print("Connected to MCP server.")
        print("Tools discovered over MCP:")
        for tool in conn.tools:
            print(f"  - {tool.name}: {tool.description}")

        client = AnthropicClient()
        transcript = await run_agent(
            client=client,
            tools=conn.tools,
            task="What is Grace Hopper's email address? Use the available tools.",
        )

    print("\n=================== SUMMARY ===================")
    print(f"stopped because: {transcript.stopped_reason}")
    print(f"tool calls made: {len(transcript.all_tool_calls())}")
    print(f"final answer: {transcript.final_text}")


if __name__ == "__main__":
    asyncio.run(main())
