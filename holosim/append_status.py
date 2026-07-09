"""Append a status note to the configured HoloChain.

This is a small utility script, not a core module. It uses the centralized
configuration path instead of hardcoding holo_memory.jsonl.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from holosim.config import ACTIVE_HASH, DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain


DEFAULT_STATUS = (
    "Canyon status 2026-07-07: HOLO-Invariant local setup verified. "
    "Continuity engine healthy."
)


def append_status(status: str = DEFAULT_STATUS) -> int:
    """Append a status note to the configured HoloChain."""
    chain = HoloChain(str(DEFAULT_CHAIN_FILE))

    entry = chain.append(
        {
            "type": "status",
            "source": "append_status",
            "active_hash": ACTIVE_HASH,
            "content": status,
        },
        compress=True,
    )

    print("Appended entry:", entry["idx"])
    print("New health:", chain.health()["recommendation"])
    return 0


def main() -> None:
    status = " ".join(sys.argv[1:]).strip() or DEFAULT_STATUS
    raise SystemExit(append_status(status))


if __name__ == "__main__":
    main()