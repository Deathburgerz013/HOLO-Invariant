"""Internal API surface for Holo/Sim.

Stable callable layer for CLI, runtime, bots, GUI, HTTP adapters, and tests.
This file stays thin: it delegates to Runtime, Service, Collector, and
Provenance instead of reimplementing subsystem logic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.provenance import get_provenance
    from holosim.runtime import get_runtime
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.provenance import get_provenance
    from holosim.runtime import get_runtime


class HoloAPI:
    """Stable internal API for Holo/Sim."""

    def __init__(
        self,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
        *,
        thread_id: str | None = None,
        source: str = "api",
    ) -> None:
        self.chain_path = Path(chain_path)
        self.thread_id = thread_id
        self.source = source
        self.runtime = get_runtime(self.chain_path)

    def provenance(self, *, source: str | None = None) -> Dict[str, Any]:
        return get_provenance(
            thread_id=self.thread_id,
            source=source or self.source,
        ).packet()

    def _with_provenance(
        self,
        result: Dict[str, Any],
        *,
        source: str | None = None,
    ) -> Dict[str, Any]:
        data = dict(result)
        data["provenance"] = self.provenance(source=source)
        return data

    def boot(self) -> Dict[str, Any]:
        return self._with_provenance(self.runtime.boot(), source="runtime.boot")

    def health(self) -> Dict[str, Any]:
        return self._with_provenance(self.runtime.health(), source="runtime.health")

    def status(self) -> Dict[str, Any]:
        return self._with_provenance(self.runtime.status(), source="runtime.status")

    def verify(self) -> Dict[str, Any]:
        return self._with_provenance(self.runtime.verify(), source="runtime.verify")

    def replay(
        self,
        *,
        last: int | None = None,
        search: str | None = None,
        timeline: bool = False,
        limit: int = 20,
    ) -> Dict[str, Any]:
        result = self.runtime.replay(
            last=last,
            search=search,
            timeline=timeline,
            limit=limit,
        )
        return self._with_provenance(result, source="runtime.replay")

    def mine(
        self,
        source_file: str | Path,
        output: str | Path,
        *,
        chunk_size: int = 40000,
    ) -> Dict[str, Any]:
        result = self.runtime.mine(source_file, output, chunk_size=chunk_size)
        return self._with_provenance(result, source="runtime.mine")

    def ingest(
        self,
        directory: str | Path,
        *,
        source: str = "api",
        force: bool = False,
        reviewer: str | None = None,
        approval_reference: str | None = None,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        result = self.runtime.ingest(
            directory,
            source=source,
            force=force,
            reviewer=reviewer,
            approval_reference=approval_reference,
            limit=limit,
        )
        return self._with_provenance(result, source="runtime.ingest")

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
        result = self.runtime.scan_once(
            watch_dir,
            output_root,
            chunk_size=chunk_size,
            force=force,
            limit_files=limit_files,
            limit_chunks=limit_chunks,
            dry_run=not live,
        )
        return self._with_provenance(result, source="runtime.scan")

    def collect(
        self,
        text: str,
        *,
        source: str = "api",
        force: bool = False,
        reviewer: str | None = None,
        approval_reference: str | None = None,
    ) -> Dict[str, Any]:
        """Collect plain text through Collector with provenance attached."""
        from holosim.collector import get_collector

        provenance = self.provenance(source=source)

        payload = {
            "type": "api_collect",
            "source": source,
            "provenance": provenance,
            "content": text,
        }

        collector = get_collector(self.chain_path)
        result = collector.collect_text(
            json.dumps(payload, ensure_ascii=False),
            source=source,
            force=force,
            reviewer=reviewer,
            approval_reference=approval_reference,
        )

        return {
            "status": result.get("status"),
            "result": result,
            "provenance": provenance,
        }


def get_api(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    thread_id: str | None = None,
    source: str = "api",
) -> HoloAPI:
    return HoloAPI(
        chain_path,
        thread_id=thread_id,
        source=source,
    )


def main() -> None:
    api = get_api()
    print(json.dumps(api.status(), indent=2))


if __name__ == "__main__":
    main()