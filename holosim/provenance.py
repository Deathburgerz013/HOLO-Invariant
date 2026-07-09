"""
holosim.provenance

Standard provenance packet builder.

Every collected artifact can carry the same identity metadata so
replay, audit, mining, runtime, and future external APIs all speak
the same language.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

try:
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        HOLOSIM_VERSION,
    )
except ImportError:
    from config import (  # type: ignore
        ACTIVE_HASH,
        ANCHOR,
        HOLOSIM_VERSION,
    )


DEFAULT_THREAD_ID = None


class Provenance:
    """Build standardized provenance metadata."""

    def __init__(
        self,
        *,
        thread_id: str | None = DEFAULT_THREAD_ID,
        source: str = "runtime",
        anchor: str = ANCHOR,
        active_hash: str = ACTIVE_HASH,
    ) -> None:
        self.thread_id = thread_id
        self.source = source
        self.anchor = anchor
        self.active_hash = active_hash

    @staticmethod
    def git_commit() -> str | None:
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                .strip()
            )
        except Exception:
            return None

    @staticmethod
    def git_branch() -> str | None:
        try:
            return (
                subprocess.check_output(
                    ["git", "branch", "--show-current"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                .strip()
            )
        except Exception:
            return None

    def packet(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "anchor": self.anchor,
            "active_hash": self.active_hash,
            "version": HOLOSIM_VERSION,
            "source": self.source,
            "git": {
                "branch": self.git_branch(),
                "commit": self.git_commit(),
            },
        }

    def attach(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return payload with provenance attached."""

        data = dict(payload)
        data["provenance"] = self.packet()
        return data


_default: Provenance | None = None


def get_provenance(
    *,
    thread_id: str | None = DEFAULT_THREAD_ID,
    source: str = "runtime",
) -> Provenance:
    global _default

    if (
        _default is None
        or _default.thread_id != thread_id
        or _default.source != source
    ):
        _default = Provenance(
            thread_id=thread_id,
            source=source,
        )

    return _default