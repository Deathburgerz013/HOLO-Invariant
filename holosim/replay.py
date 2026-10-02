"""Replay engine for Holo/Sim.

Provides clean reconstruction, searching, timeline viewing, and verification
over the configured HoloChain.
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain


MAX_SEARCH_DECODED_BYTES = 1_048_576


class SearchDecodeError(ValueError):
    """A compressed search record cannot be decoded within the byte cap."""


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
        """Match verified decoded content; return unchanged stored entries.

        Compressed content is limited to MAX_SEARCH_DECODED_BYTES per record.
        Invalid or oversized compressed records raise SearchDecodeError.
        """
        needle = query.lower().strip()
        if not needle:
            return []

        results: List[Dict[str, Any]] = []

        for entry in self.entries():
            content = self._searchable_content(entry)
            if needle in content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    @staticmethod
    def _searchable_content(entry: Dict[str, Any]) -> str:
        content = str(entry.get("content", ""))
        if entry.get("type") != "compressed":
            return content
        try:
            raw = bytes.fromhex(content)
        except ValueError as exc:
            raise SearchDecodeError("malformed hex") from exc
        try:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(raw, MAX_SEARCH_DECODED_BYTES + 1)
        except zlib.error as exc:
            raise SearchDecodeError("invalid zlib") from exc
        if len(decoded) > MAX_SEARCH_DECODED_BYTES:
            raise SearchDecodeError("decoded content exceeds limit")
        if not decoder.eof:
            raise SearchDecodeError("incomplete zlib stream")
        if decoder.unused_data:
            raise SearchDecodeError("trailing compressed data")
        try:
            return decoded.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SearchDecodeError("invalid utf-8") from exc

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