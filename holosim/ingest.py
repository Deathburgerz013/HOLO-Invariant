"""Ingest engine for Holo/Sim.

Reads mined chunk JSON files and sends their data through Collector.
This is the bridge between Miner and Collector.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from holosim.collector import get_collector
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.collector import get_collector


def load_chunk(path: str | Path) -> Dict[str, Any]:
    """Load one mined chunk JSON file."""
    chunk_path = Path(path)
    return json.loads(chunk_path.read_text(encoding="utf-8"))


def ingest_chunk(
    path: str | Path,
    *,
    source: str = "miner",
    force: bool = False,
    reviewer: str | None = None,
    approval_reference: str | None = None,
) -> Dict[str, Any]:
    """Ingest one mined chunk through Collector."""
    chunk_path = Path(path)
    chunk = load_chunk(chunk_path)

    text = str(chunk.get("data", "")).strip()
    tags = [
        "mined",
        f"chunk:{chunk.get('index')}",
        f"hash:{chunk.get('hash')}",
        chunk_path.name,
    ]

    collector = get_collector()
    result = collector.collect_text(
        text,
        source=source,
        tags=tags,
        force=force,
        reviewer=reviewer,
        approval_reference=approval_reference,
    )

    return {
        "chunk_file": str(chunk_path),
        "chunk_index": chunk.get("index"),
        "chunk_hash": chunk.get("hash"),
        "result": result,
    }


def ingest_directory(
    directory: str | Path,
    *,
    source: str = "miner",
    force: bool = False,
    limit: int | None = None,
    reviewer: str | None = None,
    approval_reference: str | None = None,
) -> Dict[str, Any]:
    """Ingest mined chunk JSON files from a directory."""
    root = Path(directory)
    files = sorted(root.glob("mine_*.json"))

    if limit is not None:
        files = files[:limit]

    results: List[Dict[str, Any]] = []

    for file_path in files:
        results.append(
            ingest_chunk(
                file_path,
                source=source,
                force=force,
                reviewer=reviewer,
                approval_reference=approval_reference,
            )
        )

    collected = sum(1 for item in results if item["result"].get("status") == "collected")
    skipped = sum(1 for item in results if item["result"].get("status") == "skipped")
    blocked = sum(1 for item in results if item["result"].get("status") == "blocked")

    return {
        "status": "ingested",
        "directory": str(root),
        "files_seen": len(files),
        "collected": collected,
        "skipped": skipped,
        "blocked": blocked,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest mined Holo/Sim chunks through Collector.")
    parser.add_argument("path", help="Mined chunk JSON file or mined directory")
    parser.add_argument("--source", default="miner", help="Source label")
    parser.add_argument("--force", action="store_true", help="Force ingest even if duplicate")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of chunks from directory")
    parser.add_argument("--reviewer", required=True, help="External reviewer identity")
    parser.add_argument(
        "--approval-reference",
        required=True,
        help="External approval record reference",
    )

    args = parser.parse_args()
    path = Path(args.path)

    if path.is_dir():
        result = ingest_directory(
            path,
            source=args.source,
            force=args.force,
            limit=args.limit,
            reviewer=args.reviewer,
            approval_reference=args.approval_reference,
        )
    else:
        result = ingest_chunk(
            path,
            source=args.source,
            force=args.force,
            reviewer=args.reviewer,
            approval_reference=args.approval_reference,
        )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()