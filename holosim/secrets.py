"""Safe secret loading for Holo/Sim.

Never hardcode API keys, Discord tokens, or private bridge secrets in source.
"""

from __future__ import annotations

import os
from typing import Optional


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a secret from environment variables."""
    value = os.getenv(name)
    return value if value not in {"", None} else default


def require_secret(name: str) -> str:
    """Read a required secret or raise a clear error."""
    value = get_secret(name)
    if not value:
        raise RuntimeError(f"Missing required secret: {name}")
    return value


def discord_token() -> str:
    return require_secret("HOLOSIM_DISCORD_TOKEN")


def bridge_secret() -> str:
    return require_secret("HOLOSIM_BRIDGE_SECRET")


def openai_api_key() -> str:
    return require_secret("OPENAI_API_KEY")