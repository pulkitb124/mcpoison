"""Loads API keys and configuration from the local `.env` file.

Keys live only in `.env` (which is gitignored). Nothing here ever prints a key.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

PROVIDER_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def get_key(provider: str) -> str | None:
    """Return the API key for a provider, or None if it isn't set."""
    env_var = PROVIDER_ENV_VARS.get(provider)
    if env_var is None:
        raise ValueError(f"Unknown provider {provider!r}. Known: {list(PROVIDER_ENV_VARS)}")
    key = os.getenv(env_var)
    return key or None


def configured_providers() -> list[str]:
    """Return the providers that currently have a non-empty key."""
    return [p for p in PROVIDER_ENV_VARS if get_key(p)]
