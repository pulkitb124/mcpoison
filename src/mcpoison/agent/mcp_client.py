"""Connection to an MCP server, exposing its remote tools to the agent loop.

Usage:
    async with MCPConnection.for_module("mcpoison.servers.benign") as conn:
        await run_agent(client, conn.tools, task)
"""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, stdio_client

from .tools import Tool


def _extract_text(result) -> str:
    """Flatten an MCP tool result into the plain string our loop expects."""
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    structured = getattr(result, "structured_content", None)
    return str(structured) if structured is not None else ""


def _tool_schema(mcp_tool) -> dict:
    schema = getattr(mcp_tool, "input_schema", None) or getattr(mcp_tool, "inputSchema", None)
    return schema or {"type": "object", "properties": {}}


class MCPConnection:
    """A live async connection to one MCP server, presenting its tools."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ):
        self._params = StdioServerParameters(
            command=command, args=list(args or []), env=env, cwd=cwd
        )
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self.tools: list[Tool] = []

    @classmethod
    def for_module(cls, module: str, **kwargs) -> MCPConnection:
        """Build a connection object for a server run as `python -m <module>` (same venv).

        This only configures the connection; entering the `async with` block is
        what actually launches the server and connects.
        """
        return cls(command=sys.executable, args=["-m", module], **kwargs)

    async def __aenter__(self) -> MCPConnection:
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        listed = await self._session.list_tools()
        self.tools = [self._wrap(t) for t in listed.tools]
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._stack.aclose()

    def _wrap(self, mcp_tool) -> Tool:
        name = mcp_tool.name

        async def handler(arguments: dict) -> str:
            result = await self._session.call_tool(name, arguments)
            return _extract_text(result)

        return Tool(
            name=name,
            description=mcp_tool.description or "",
            input_schema=_tool_schema(mcp_tool),
            handler=handler,
        )
