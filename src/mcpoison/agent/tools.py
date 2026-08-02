"""The tool abstraction.

A tool is a name, a natural-language description, a JSON-schema for its inputs,
and a handler that actually does the work. The model reads the name + description
+ schema to decide whether and how to call it, which is exactly why the
*description* is an attack surface we'll study later.

Handlers may be either plain (sync) functions or async coroutines. Local
in-process tools are usually sync; MCP-backed tools are async (they await a call
to a remote server). `run` accepts both so the agent loop doesn't have to care.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str | Awaitable[str]]

    async def run(self, arguments: dict) -> str:
        result = self.handler(arguments)
        if inspect.isawaitable(result):
            return await result
        return result
