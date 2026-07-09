"""Internal API surface for Holo/Sim.

Stable callable layer for CLI, runtime, bots, GUI, HTTP adapters, and tests.
This file should stay thin: it delegates to Runtime and Service instead of
reimplementing subsystem logic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.runtime import get_runtime
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.runtime import get_runtime


class HoloAPI:
    """Stable internal API for Holo/Sim."""

    def __init__(self, chain_path: str | Path = DEFAULT_CHAIN_FILE) -> None:
        self.chain_path = Path(chain_path)
        self.runtime = get_runtime(self.chain_path)

    def boot(self) -> Dict[str, Any]:
        return self.runtime.boot()

    def health(self) -> Dict[str, Any]:
        return self.runtime.health()

    def status(self) -> Dict[str, Any]:
        return self.runtime.status()

    def verify(self) -> Dict[str, Any]:
        return self.runtime.verify()

    def replay(
        self,
        *,
        last: int | None = None,
        search: str | None = None,
        timeline: bool = False,
        limit: int = 20,
    ) -> Dict[str, Any]:
        return self.runtime.replay(
            last=last,
            search=search,
            timeline=timeline,
            limit=limit,
        )

    def mine(
        self,
        source: str | Path,
        output: str | Path,
        *,
        chunk_size: int = 40000,
    ) -> Dict[str, Any]:
        return self.runtime.mine(source, output, chunk_size=chunk_size)

    def ingest(
        self,
        directory: str | Path,
        *,
        source: str = "api",
        force: bool = False,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        return self.runtime.ingest(
            directory,
            source=source,
            force=force,
            limit=limit,
        )

    def scan(
        self,
        watch_dir: str | Path,
        output_root: str | Path,
        *,
        chunk_size: int = 40000,
        force: bool = False,
        limit_files: int | None = None,
        limit_chunks: int | None = None,
        live: bool = False,
    ) -> Dict[str, Any]:
        return self.runtime.scan_once(
            watch_dir,
            output_root,
            chunk_size=chunk_size,
            force=force,
            limit_files=limit_files,
            limit_chunks=limit_chunks,
            dry_run=not live,
        )

    def collect(
        self,
        text: str,
        *,
        source: str = "api",
        force: bool = False,
    ) -> Dict[str, Any]:
        """Collect plain text through Collector via Runtime service path."""
        from holosim.collector import get_collector

        collector = get_collector(self.chain_path)
        return collector.collect_text(
            text,
            source=source,
            force=force,
        )


def get_api(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> HoloAPI:
    return HoloAPI(chain_path)


def main() -> None:
    api = get_api()
    print(json.dumps(api.status(), indent=2))


if __name__ == "__main__":
    main()