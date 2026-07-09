"""Scheduler engine for Holo/Sim.

Runs controlled one-shot jobs over existing Holo/Sim subsystems.
This is not a background daemon yet. It is the safe bridge before daemon mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.ingest import ingest_directory
    from holosim.miner import mine_file
    from holosim.service import get_service
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.ingest import ingest_directory
    from holosim.miner import mine_file
    from holosim.service import get_service


def run_health(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> Dict[str, Any]:
    """Run service health check."""
    service = get_service(chain_path)
    return {
        "job": "health",
        "status": "complete",
        "health": service.health(),
        "verify": service.verify(),
    }


def run_mine(
    source: str | Path,
    output: str | Path,
    *,
    chunk_size: int = 40000,
) -> Dict[str, Any]:
    """Run miner job."""
    return {
        "job": "mine",
        "status": "complete",
        "result": mine_file(source, output, chunk_size=chunk_size),
    }


def run_ingest(
    directory: str | Path,
    *,
    source: str = "scheduler",
    force: bool = False,
    limit: int | None = None,
) -> Dict[str, Any]:
    """Run ingest job."""
    return {
        "job": "ingest",
        "status": "complete",
        "result": ingest_directory(
            directory,
            source=source,
            force=force,
            limit=limit,
        ),
    }


def run_mine_ingest(
    source: str | Path,
    output: str | Path,
    *,
    chunk_size: int = 40000,
    force: bool = False,
    limit: int | None = None,
) -> Dict[str, Any]:
    """Run mine then ingest as one controlled pipeline."""
    mine_result = mine_file(source, output, chunk_size=chunk_size)
    ingest_result = ingest_directory(
        output,
        source="scheduler",
        force=force,
        limit=limit,
    )

    service = get_service()

    return {
        "job": "mine-ingest",
        "status": "complete",
        "mine": mine_result,
        "ingest": ingest_result,
        "verify": service.verify(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Holo/Sim scheduled jobs once.")
    subparsers = parser.add_subparsers(dest="job", required=True)

    subparsers.add_parser("health", help="Run health and verification job")

    mine_parser = subparsers.add_parser("mine", help="Mine a file into chunks")
    mine_parser.add_argument("source")
    mine_parser.add_argument("output")
    mine_parser.add_argument("--chunk-size", type=int, default=40000)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a mined directory")
    ingest_parser.add_argument("directory")
    ingest_parser.add_argument("--source", default="scheduler")
    ingest_parser.add_argument("--force", action="store_true")
    ingest_parser.add_argument("--limit", type=int, default=None)

    pipeline_parser = subparsers.add_parser("mine-ingest", help="Mine a file then ingest chunks")
    pipeline_parser.add_argument("source")
    pipeline_parser.add_argument("output")
    pipeline_parser.add_argument("--chunk-size", type=int, default=40000)
    pipeline_parser.add_argument("--force", action="store_true")
    pipeline_parser.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    if args.job == "health":
        result = run_health()
    elif args.job == "mine":
        result = run_mine(args.source, args.output, chunk_size=args.chunk_size)
    elif args.job == "ingest":
        result = run_ingest(
            args.directory,
            source=args.source,
            force=args.force,
            limit=args.limit,
        )
    elif args.job == "mine-ingest":
        result = run_mine_ingest(
            args.source,
            args.output,
            chunk_size=args.chunk_size,
            force=args.force,
            limit=args.limit,
        )
    else:
        raise SystemExit(f"Unknown job: {args.job}")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()