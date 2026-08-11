"""Runtime coordinator for Holo/Sim.

Boots and exposes the main runtime services through one command surface.
This is not a forever daemon yet. It is a safe runtime conductor.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

try:
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.correction_cycle import build_correction_cycle
    from holosim.ingest import ingest_directory
    from holosim.miner import mine_file
    from holosim.reconstructor import build_reconstructed_state, build_reconstruction_manifest
    from holosim.scheduler import run_health
    from holosim.service import get_service
    from holosim.watcher import watch_once
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.correction_cycle import build_correction_cycle
    from holosim.ingest import ingest_directory
    from holosim.miner import mine_file
    from holosim.reconstructor import build_reconstructed_state, build_reconstruction_manifest
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
        return {
            "status": "booted",
            "identity": self.identity(),
            "health": run_health(self.chain_path),
            "timestamp": int(time.time()),
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "identity": self.identity(),
            "health": self.service.health(),
            "timestamp": int(time.time()),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "identity": self.identity(),
            "service": self.service.status(),
            "timestamp": int(time.time()),
        }

    def verify(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "identity": self.identity(),
            "verify": self.service.verify(),
            "timestamp": int(time.time()),
        }

    def replay(
        self,
        *,
        last: int | None = None,
        search: str | None = None,
        timeline: bool = False,
        limit: int = 20,
    ) -> Dict[str, Any]:
        if search:
            result = self.service.search(search, limit=limit)
        elif timeline:
            result = self.service.replay_timeline()
        elif last is not None:
            result = self.service.replay.last(last)
        else:
            result = self.service.verify()

        return {
            "status": "ok",
            "identity": self.identity(),
            "replay": result,
            "timestamp": int(time.time()),
        }

    def reference_loop(
        self,
        *,
        reference: str,
        target_ids: Sequence[str],
        prior_items: Sequence[Mapping[str, Any]],
        observations: Sequence[Sequence[Mapping[str, Any]]],
    ) -> Dict[str, Any]:
        """Run a bounded, read-only reconstruction/correction observation loop.

        The runtime reconstructs only explicit dependencies from ``prior_items``,
        compares that carried state against each supplied observation in order,
        and delegates stopping semantics to the correction cycle. It does not
        choose hooks, execute corrections, mutate observations, grant acceptance,
        or grant write authority.
        """
        if type(observations) not in {list, tuple} or not observations:
            raise ValueError("observations must be a nonempty list or tuple")

        reconstructed = build_reconstructed_state(reference, target_ids, prior_items)
        manifests = []
        for observation in observations:
            manifest = build_reconstruction_manifest(
                reconstructed["reference"],
                reconstructed["carried_items"],
                observation,
            )
            manifests.append(manifest)
            if not manifest["changed"] and not manifest["missing_ids"]:
                break

        cycle = build_correction_cycle(reconstructed["reference"], manifests)
        return {
            "status": cycle["status"],
            "identity": self.identity(),
            "reference": reconstructed["reference"],
            "reconstructed_state": reconstructed,
            "manifests": manifests,
            "correction_cycle": cycle,
            "accepted": False,
            "write_authority": "NONE",
            "interpretation_notice": (
                "The runtime coordinates existing reconstruction and correction "
                "observations only. It does not choose or execute hooks, apply "
                "corrections, establish truth, acceptance, or authority."
            ),
            "timestamp": int(time.time()),
        }

    def mine(
        self,
        source: str | Path,
        output: str | Path,
        *,
        chunk_size: int = 40000,
    ) -> Dict[str, Any]:
        return {
            "status": "mined",
            "identity": self.identity(),
            "mine": mine_file(source, output, chunk_size=chunk_size),
            "timestamp": int(time.time()),
        }

    def ingest(
        self,
        directory: str | Path,
        *,
        source: str = "runtime",
        force: bool = False,
        reviewer: str | None = None,
        approval_reference: str | None = None,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        result = ingest_directory(
            directory,
            source=source,
            force=force,
            limit=limit,
            reviewer=reviewer,
            approval_reference=approval_reference,
            chain_path=self.chain_path,
        )
        return {
            "status": "ingested",
            "identity": self.identity(),
            "ingest": result,
            "verify": self.service.verify(),
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
        scan = watch_once(
            watch_dir,
            output_root,
            chunk_size=chunk_size,
            force=force,
            limit_files=limit_files,
            limit_chunks=limit_chunks,
            dry_run=dry_run,
        )

        return {
            "status": "scan_complete",
            "identity": self.identity(),
            "scan": scan,
            "verify": self.service.verify(),
            "timestamp": int(time.time()),
        }


def get_runtime(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> HoloRuntime:
    return HoloRuntime(chain_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Holo/Sim runtime coordinator.")
    parser.add_argument("--file", "-f", default=str(DEFAULT_CHAIN_FILE), help="Chain file path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("boot", help="Boot runtime and verify services")
    subparsers.add_parser("health", help="Show runtime health")
    subparsers.add_parser("status", help="Show runtime/service status")
    subparsers.add_parser("verify", help="Verify runtime chain")

    replay_parser = subparsers.add_parser("replay", help="Replay or inspect chain")
    replay_parser.add_argument("--last", type=int, default=None)
    replay_parser.add_argument("--search", default=None)
    replay_parser.add_argument("--timeline", action="store_true")
    replay_parser.add_argument("--limit", type=int, default=20)

    mine_parser = subparsers.add_parser("mine", help="Mine a file into chunks")
    mine_parser.add_argument("source")
    mine_parser.add_argument("output")
    mine_parser.add_argument("--chunk-size", type=int, default=40000)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a mined directory")
    ingest_parser.add_argument("directory")
    ingest_parser.add_argument("--source", default="runtime")
    ingest_parser.add_argument("--force", action="store_true")
    ingest_parser.add_argument("--limit", type=int, default=None)

    scan_parser = subparsers.add_parser("scan", help="Run one watcher scan")
    scan_parser.add_argument("watch_dir")
    scan_parser.add_argument("output_root")
    scan_parser.add_argument("--chunk-size", type=int, default=40000)
    scan_parser.add_argument("--force", action="store_true")
    scan_parser.add_argument("--limit-files", type=int, default=None)
    scan_parser.add_argument("--limit-chunks", type=int, default=None)
    scan_parser.add_argument("--live", action="store_true")

    args = parser.parse_args()
    runtime = get_runtime(args.file)

    if args.command == "boot":
        result = runtime.boot()
    elif args.command == "health":
        result = runtime.health()
    elif args.command == "status":
        result = runtime.status()
    elif args.command == "verify":
        result = runtime.verify()
    elif args.command == "replay":
        result = runtime.replay(
            last=args.last,
            search=args.search,
            timeline=args.timeline,
            limit=args.limit,
        )
    elif args.command == "mine":
        result = runtime.mine(args.source, args.output, chunk_size=args.chunk_size)
    elif args.command == "ingest":
        result = runtime.ingest(
            args.directory,
            source=args.source,
            force=args.force,
            limit=args.limit,
        )
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
