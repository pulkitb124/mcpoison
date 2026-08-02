"""A benign MCP server that exposes a couple of harmless tools over stdio.

This is a *real* MCP server. Our agent connects to it as an MCP client, asks
for its tool list, and calls the tools over the protocol, exactly as it would
with any third-party server. Later we'll add a malicious counterpart that hides
instructions in a tool's description or output.

The tool's description and input schema are generated automatically from the
function's docstring and type hints by the `@server.tool()` decorator.

Run standalone for debugging:
    python -m mcpoison.servers.benign
"""

from __future__ import annotations

from mcp.server import MCPServer

server = MCPServer(name="benign-directory", version="0.1.0")

_DIRECTORY = {
    "ada lovelace": "ada@example.com",
    "alan turing": "alan@example.com",
    "grace hopper": "grace@example.com",
}


@server.tool()
def lookup_email(name: str) -> str:
    """Look up an employee's email address by their full name."""
    return _DIRECTORY.get(name.strip().lower(), f"No directory entry found for {name!r}.")


@server.tool()
def list_employees() -> str:
    """List the full names of every employee in the directory."""
    return ", ".join(sorted(n.title() for n in _DIRECTORY))


if __name__ == "__main__":
    server.run(transport="stdio")
