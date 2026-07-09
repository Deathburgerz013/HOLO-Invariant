"""Runtime coordinator for Holo/Sim.

Boots the main runtime services in one controlled pass.
This is not a forever daemon yet. It is a safe runtime conductor.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

try:
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.scheduler import run_health
    from holosim.service import get_service
    from holosim.watcher import watch_once
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.scheduler import run_health
    from holosim.service import get_service
    from holosim.watcher import watch_once


class HoloRuntime:
    """One-command runtime coordinator."""

    def __init__(self, chain_path: str | Path = DEFAULT_CHAIN_FILE) -> None:
        self.chain_path = Path(chain_path)
        self.service = get_service(self.chain_path)

    def identity(self) -> Dict[str, Any]:
        return {
            "runtime": "HoloRuntime",
            "system": "Holo/Sim",
            "version": HOLOSIM_VERSION,
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "chain_file": str(self.chain_path),
        }

    def boot(self) -> Dict[str, Any]:
        """Boot runtime and verify core services."""
        health = run_health(self.chain_path)

        return {
            "status": "booted",
            "identity": self.identity(),
            "health": health,
            "timestamp": int(time.time()),
        }

    def scan_once(
        self,
        watch_dir: str | Path,
        output_root: str | Path,
        *,
        chunk_size: int = 40000,
        force: bool = False,
        limit_files: int | None = None,
        limit_chunks: int | None = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Run one watcher scan from runtime."""
        scan = watch_once(
            watch_dir,
            output_root,
            chunk_size=chunk_size,
            force=force,
            limit_files=limit_files,
            limit_chunks=limit_chunks,
            dry_run=dry_run,
        )

        verify = self.service.verify()

        return {
            "status": "scan_complete",
            "identity": self.identity(),
            "scan": scan,
            "verify": verify,
            "timestamp": int(time.time()),
        }


def get_runtime(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> HoloRuntime:
    """Create HoloRuntime."""
    return HoloRuntime(chain_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Holo/Sim runtime coordinator.")
    parser.add_argument("--file", "-f", default=str(DEFAULT_CHAIN_FILE), help="Chain file path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("boot", help="Boot runtime and verify services")

    scan_parser = subparsers.add_parser("scan", help="Run one watcher scan")
    scan_parser.add_argument("watch_dir")
    scan_parser.add_argument("output_root")
    scan_parser.add_argument("--chunk-size", type=int, default=40000)
    scan_parser.add_argument("--force", action="store_true")
    scan_parser.add_argument("--limit-files", type=int, default=None)
    scan_parser.add_argument("--limit-chunks", type=int, default=None)
    scan_parser.add_argument("--live", action="store_true", help="Actually ingest instead of dry-run")

    args = parser.parse_args()
    runtime = get_runtime(args.file)

    if args.command == "boot":
        result = runtime.boot()
    elif args.command == "scan":
        result = runtime.scan_once(
            args.watch_dir,
            args.output_root,
            chunk_size=args.chunk_size,
            force=args.force,
            limit_files=args.limit_files,
            limit_chunks=args.limit_chunks,
            dry_run=not args.live,
        )
    else:
        raise SystemExit(f"Unknown runtime command: {args.command}")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()