"""Delta export format for Holo/Sim.

Creates portable continuity packets that can later be handed to model providers,
local runtimes, IPFS, ledgers, archives, or other persistence systems without
locking Holo/Sim to one vendor.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

try:
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.provenance import get_provenance
    from holosim.replay import ReplayEngine
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.provenance import get_provenance
    from holosim.replay import ReplayEngine


DELTA_EXPORT_TYPE = "holo_delta_export"
DELTA_EXPORT_VERSION = "0.1"


def stable_payload_hash(payload: Any) -> str:
    """Hash a JSON-like payload in a deterministic way."""
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_delta_export(
    payload: Any,
    *,
    thread_id: str | None = None,
    source: str = "delta_export",
    label: str | None = None,
) -> Dict[str, Any]:
    """Build a portable Holo/Sim delta export packet."""
    payload_hash = stable_payload_hash(payload)
    provenance = get_provenance(thread_id=thread_id, source=source).packet()

    packet = {
        "type": DELTA_EXPORT_TYPE,
        "version": DELTA_EXPORT_VERSION,
        "label": label,
        "anchor": ANCHOR,
        "active_hash": ACTIVE_HASH,
        "holosim_version": HOLOSIM_VERSION,
        "thread_id": thread_id,
        "source": source,
        "created_at": int(time.time()),
        "payload_hash": payload_hash,
        "provenance": provenance,
        "payload": payload,
    }

    packet["export_hash"] = stable_payload_hash(
        {k: v for k, v in packet.items() if k != "export_hash"}
    )
    return packet


def export_latest(
    *,
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    thread_id: str | None = None,
    source: str = "delta_export.latest",
) -> Dict[str, Any]:
    """Export the latest verified chain entry."""
    replay = ReplayEngine(chain_path)
    latest = replay.latest()

    return build_delta_export(
        latest,
        thread_id=thread_id,
        source=source,
        label="latest_entry",
    )


def export_range(
    start: int,
    end: int | None = None,
    *,
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    thread_id: str | None = None,
    source: str = "delta_export.range",
) -> Dict[str, Any]:
    """Export a verified chain range."""
    replay = ReplayEngine(chain_path)
    entries = replay.range(start, end)

    return build_delta_export(
        entries,
        thread_id=thread_id,
        source=source,
        label="entry_range",
    )


def write_delta_export(packet: Dict[str, Any], output: str | Path) -> Path:
    """Write delta export packet to disk."""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> None:
    packet = export_latest()
    print(json.dumps(packet, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()