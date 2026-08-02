"""Scenario servers: MCP servers that bundle a realistic task environment,
sensitive data, and (optionally) a planted indirect-prompt-injection attack.
"""

from __future__ import annotations

_BUILDERS = {
    "devops": "mcpoison.scenarios.devops",
    "support": "mcpoison.scenarios.support",
}


def all_scenario_ids() -> list[str]:
    return list(_BUILDERS)


def get_scenario(scenario_id: str):
    """Return the built `Scenario` for the given id."""
    import importlib

    try:
        module_name = _BUILDERS[scenario_id]
    except KeyError:
        known = ", ".join(_BUILDERS)
        raise KeyError(f"unknown scenario {scenario_id!r}; known: {known}") from None
    return importlib.import_module(module_name).build_scenario()

