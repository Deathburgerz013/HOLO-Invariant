"""Replay engine for Holo/Sim.

Provides clean reconstruction, searching, timeline viewing, and verification
over the configured HoloChain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain


class ReplayEngine:
    """Read-only replay and inspection layer for HoloChain."""

    def __init__(self, chain_path: str | Path = DEFAULT_CHAIN_FILE) -> None:
        self.chain_path = Path(chain_path)
        self.chain = HoloChain(str(self.chain_path))

    def verify(self) -> Dict[str, Any]:
        """Verify chain and return compact verification result."""
        entries = self.chain.load_and_verify()
        latest = entries[-1] if entries else None

        return {
            "status": "ok",
            "chain_file": str(self.chain_path),
            "entries": len(entries),
            "latest_idx": latest.get("idx") if latest else None,
            "latest_hash": latest.get("hash") if latest else None,
        }

    def entries(self) -> List[Dict[str, Any]]:
        """Return verified raw chain entries."""
        return self.chain.load_and_verify()

    def state(self) -> List[Any]:
        """Return reconstructed state."""
        return self.chain.get_state()

    def latest(self) -> Optional[Dict[str, Any]]:
        """Return latest verified entry."""
        return self.chain.get_latest()

    def range(self, start: int = 1, end: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return entries from start to end, inclusive."""
        if start < 1:
            start = 1

        entries = self.entries()

        if end is None:
            end = len(entries)

        return [entry for entry in entries if start <= int(entry.get("idx", 0)) <= end]

    def last(self, count: int = 10) -> List[Dict[str, Any]]:
        """Return latest N entries."""
        if count <= 0:
            return []
        return self.entries()[-count:]

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search verified raw entries by content text."""
        needle = query.lower().strip()
        if not needle:
            return []

        results: List[Dict[str, Any]] = []

        for entry in self.entries():
            content = str(entry.get("content", ""))
            if needle in content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def timeline(self) -> List[Dict[str, Any]]:
        """Return compact timeline view."""
        compact: List[Dict[str, Any]] = []

        for entry in self.entries():
            content = str(entry.get("content", ""))
            compact.append(
                {
                    "idx": entry.get("idx"),
                    "timestamp": entry.get("timestamp"),
                    "type": entry.get("type", "plain"),
                    "hash": entry.get("hash"),
                    "preview": content[:120] + ("..." if len(content) > 120 else ""),
                }
            )

        return compact

    def print_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Print compact entries to stdout."""
        for entry in entries:
            content = str(entry.get("content", ""))
            preview = content[:160] + ("..." if len(content) > 160 else "")
            print(
                f"{int(entry.get('idx', 0)):4d} | "
                f"{entry.get('timestamp')} | "
                f"{entry.get('type', 'plain')} | "
                f"{preview}"
            )


def get_replay(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> ReplayEngine:
    """Create a ReplayEngine."""
    return ReplayEngine(chain_path)


def main() -> None:
    replay = get_replay()
    print(json.dumps(replay.verify(), indent=2))


if __name__ == "__main__":
    main()