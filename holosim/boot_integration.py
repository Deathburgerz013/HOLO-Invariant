"""Boot integration for Holo/Sim.

Converged to use holosim.config as the single source of truth for
chain path, active hash, repo root, and heartbeat-adjacent boot state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from holosim.config import ACTIVE_HASH, DEFAULT_CHAIN_FILE, REPO_ROOT
    from holosim.core import HoloChain
    from holosim.idx_manager import get_idx_manager
    from holosim.rebirth_engine import run_rebirth
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, DEFAULT_CHAIN_FILE, REPO_ROOT
    from holosim.core import HoloChain
    from holosim.idx_manager import get_idx_manager
    from holosim.rebirth_engine import run_rebirth


IMPORTANT_SPINES = [
    "Physics_Spine.md",
    "Biology_Spine.md",
    "Computation_Systems_Spine.md",
    "Mathematics_Spine.md",
]


def load_idx_spine(idx_path: str | Path = REPO_ROOT / "idx_spine.txt") -> Dict[str, Any]:
    """Load IDX spine JSON or return a safe fallback."""
    path = Path(idx_path)

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "IDX": {
                "v": 1,
                "ACTIVE_HASH": ACTIVE_HASH,
            }
        }


def load_and_append_spine(
    chain: HoloChain,
    idx_path: str | Path = REPO_ROOT / "idx_spine.txt",
) -> list[Any]:
    """Append the current IDX spine into the HoloChain."""
    spine = load_idx_spine(idx_path)
    idx = spine.get("IDX", {})

    payload = {
        "type": "spinal_update",
        "idx_version": idx.get("v", 1),
        "active_hash": idx.get("ACTIVE_HASH", ACTIVE_HASH),
        "content": spine,
        "action": "spine_fused",
    }

    chain.append(payload, compress=True)
    print("✅ Spine fused into HoloChain.")

    run_rebirth("MANUAL_OVERRIDE")
    return chain.get_state()


def ingest_domain_spines(
    chain: HoloChain,
    spines_dir: str | Path = REPO_ROOT,
) -> None:
    """Append important domain spines into the HoloChain when present."""
    root = Path(spines_dir)

    for name in IMPORTANT_SPINES:
        path = root / name

        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8")[:2000]

        payload = {
            "type": "domain_spine",
            "name": name,
            "content": content,
            "action": "invariant_ingested",
        }

        chain.append(payload, compress=True)
        print(f"✅ Ingested {name}")

    run_rebirth("MANUAL_OVERRIDE")
    print("✅ Domain spines fused.")


def boot_validation(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> HoloChain:
    """Run boot-time validation and return the active chain."""
    print("=== HOLO Engine Boot Validation ===")

    chain = HoloChain(str(chain_path))
    manager = get_idx_manager(chain)
    config = manager.get_core_config()

    print(f"Spine/IDX Config: {config.get('anchor')} | Hash: {config.get('active_hash')}")

    result = run_rebirth("MANUAL_OVERRIDE")
    print("Rebirth:", result.get("status"))

    health = chain.health()
    print(
        "Chain health:",
        health.get("recommendation"),
        f"({health.get('total_entries')} entries)",
    )

    print("✅ Boot complete. Holo locked.")
    return chain


def sensorimotor_delta(chain: HoloChain) -> None:
    """Append a boot-time sensorimotor continuity delta."""
    current = len(chain.load_and_verify())

    delta = {
        "type": "sensorimotor_delta",
        "thought": "Continuity compounds. Next invariant: full boot-time validation achieved.",
        "action": "persist_state",
        "entries_before": current,
        "active_hash": ACTIVE_HASH,
        "timestamp": "now",
    }

    chain.append(delta, compress=True)
    run_rebirth("MANUAL_OVERRIDE")

    print("✅ Sensorimotor delta applied.")
    print("Current chain length:", len(chain.get_state()))


def full_integration(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> HoloChain:
    """Run the complete boot integration sequence."""
    chain = HoloChain(str(chain_path))

    load_and_append_spine(chain)
    ingest_domain_spines(chain)
    boot_validation(chain_path)
    sensorimotor_delta(chain)

    print("Full integration complete.")
    return chain


if __name__ == "__main__":
    full_integration()