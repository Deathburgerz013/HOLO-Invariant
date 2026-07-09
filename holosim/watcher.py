"""Watcher engine for Holo/Sim.

Scans a folder for source files and runs one controlled mine+ingest pass.
This is not a permanent daemon yet. It is a safe one-shot watcher.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from holosim.scheduler import run_mine_ingest
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.scheduler import run_mine_ingest


DEFAULT_SUFFIXES = {".txt", ".md", ".json", ".jsonl"}


def scan_sources(
    watch_dir: str | Path,
    *,
    suffixes: Iterable[str] = DEFAULT_SUFFIXES,
) -> List[Path]:
    """Find candidate source files in a watch directory."""
    root = Path(watch_dir)
    allowed = {suffix.lower() for suffix in suffixes}

    if not root.exists():
        return []

    files: List[Path] = []

    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed:
            continue
        files.append(path)

    return files


def watch_once(
    watch_dir: str | Path,
    output_root: str | Path,
    *,
    chunk_size: int = 40000,
    force: bool = False,
    limit_files: int | None = None,
    limit_chunks: int | None = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run one scan over a directory and optionally mine+ingest each file."""
    sources = scan_sources(watch_dir)

    if limit_files is not None:
        sources = sources[:limit_files]

    results: List[Dict[str, Any]] = []

    for source in sources:
        output_dir = Path(output_root) / f"{source.stem}_mined"

        if dry_run:
            results.append(
                {
                    "source": str(source),
                    "output": str(output_dir),
                    "status": "planned",
                }
            )
            continue

        result = run_mine_ingest(
            source,
            output_dir,
            chunk_size=chunk_size,
            force=force,
            limit=limit_chunks,
        )

        results.append(
            {
                "source": str(source),
                "output": str(output_dir),
                "status": result.get("status"),
                "result": result,
            }
        )

    return {
        "status": "complete",
        "watch_dir": str(Path(watch_dir)),
        "output_root": str(Path(output_root)),
        "files_seen": len(sources),
        "dry_run": dry_run,
        "results": results,
        "timestamp": int(time.time()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Holo/Sim watcher scan.")
    parser.add_argument("watch_dir", help="Directory to scan for input files")
    parser.add_argument("output_root", help="Directory for mined chunk output")
    parser.add_argument("--chunk-size", type=int, default=40000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--limit-chunks", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    result = watch_once(
        args.watch_dir,
        args.output_root,
        chunk_size=args.chunk_size,
        force=args.force,
        limit_files=args.limit_files,
        limit_chunks=args.limit_chunks,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()