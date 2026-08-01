"""The tool abstraction.

A tool is a name, a natural-language description, a JSON-schema for its inputs,
and a handler that actually does the work. The model reads the name + description
+ schema to decide whether and how to call it — which is exactly why the
*description* is an attack surface we'll study later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]

    def run(self, arguments: dict) -> str:
        return self.handler(arguments)
