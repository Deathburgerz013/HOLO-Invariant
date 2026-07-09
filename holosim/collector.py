"""Collection engine for Holo/Sim.

Raw input enters here. Collector deduplicates, wraps it with provenance,
appends through HoloService, then verifies the chain.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

try:
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE
    from holosim.embeddings import should_ingest
    from holosim.service import get_service
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE
    from holosim.embeddings import should_ingest
    from holosim.service import get_service


class Collector:
    """Safe intake layer for Holo/Sim continuity material."""

    def __init__(self, chain_path: str | Path = DEFAULT_CHAIN_FILE) -> None:
        self.chain_path = Path(chain_path)
        self.service = get_service(self.chain_path)

    def collect_text(
        self,
        text: str,
        *,
        source: str = "manual",
        tags: Iterable[str] | None = None,
        threshold: float = 0.85,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Collect text into HoloChain if it is not a near-duplicate."""
        clean_text = text.strip()

        if not clean_text:
            return {
                "status": "skipped",
                "reason": "empty_input",
            }

        state = self.service.replay_timeline()
        ingest_ok = force or should_ingest(clean_text, state, threshold=threshold)

        if not ingest_ok:
            return {
                "status": "skipped",
                "reason": "duplicate_or_near_duplicate",
                "threshold": threshold,
            }

        payload = {
            "type": "collected_text",
            "source": source,
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "tags": list(tags or []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": clean_text,
        }

        append_result = self.service.append(payload, compress=True)
        verify_result = self.service.verify()

        return {
            "status": "collected",
            "append": append_result,
            "verify": verify_result,
        }

    def collect_file(
        self,
        path: str | Path,
        *,
        source: str = "file",
        tags: Iterable[str] | None = None,
        threshold: float = 0.85,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Collect text from a file."""
        file_path = Path(path)

        if not file_path.exists():
            return {
                "status": "skipped",
                "reason": "file_not_found",
                "path": str(file_path),
            }

        text = file_path.read_text(encoding="utf-8", errors="replace")

        return self.collect_text(
            text,
            source=source,
            tags=[*(tags or []), file_path.name],
            threshold=threshold,
            force=force,
        )


def get_collector(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> Collector:
    """Create Collector."""
    return Collector(chain_path)


if __name__ == "__main__":
    collector = get_collector()
    print(collector.collect_text("Collector smoke test", source="cli", tags=["smoke"], force=True))