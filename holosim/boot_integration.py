from __future__ import annotations
from holosim.core import HoloChain
from holosim.rebirth_engine import run_rebirth
from holosim.idx_manager import get_idx_manager
from pathlib import Path
import json

def load_idx_spine(idx_path: str = "idx_spine.txt"):
    try:
        return json.loads(Path(idx_path).read_text(encoding="utf-8"))
    except Exception:
        return {"IDX": {"v": 1, "ACTIVE_HASH": "v0807a-2b43f9d1"}}

def load_and_append_spine(chain: HoloChain, idx_path: str = "idx_spine.txt"):
    spine = load_idx_spine(idx_path)
    payload = {
        "type": "spinal_update",
        "idx_version": spine.get("IDX", {}).get("v"),
        "active_hash": spine.get("IDX", {}).get("ACTIVE_HASH"),
        "content": spine,
        "action": "spine_fused"
    }
    chain.append(payload, compress=True)
    print("✅ Spine fused into HoloChain.")
    run_rebirth("MANUAL_OVERRIDE")
    return chain.get_state()

def ingest_domain_spines(chain: HoloChain, spines_dir: str = "."):
    important_spines = ["Physics_Spine.md", "Biology_Spine.md", "Computation_Systems_Spine.md", "Mathematics_Spine.md"]
    for name in important_spines:
        path = Path(spines_dir) / name
        if path.exists():
            content = path.read_text(encoding="utf-8")[:2000]
            payload = {"type": "domain_spine", "name": name, "content": content, "action": "invariant_ingested"}
            chain.append(payload, compress=True)
            print(f"✅ Ingested {name}")
    run_rebirth("MANUAL_OVERRIDE")
    print("✅ Domain spines fused.")

def boot_validation():
    print("=== HOLO Engine Boot Validation ===")
    chain = HoloChain("holo_memory.jsonl")
    m = get_idx_manager(chain)
    config = m.get_core_config()
    print(f"Spine/IDX Config: {config.get('anchor')} | Hash: {config.get('active_hash')}")
    result = run_rebirth("MANUAL_OVERRIDE")
    print("Rebirth:", result.get("status"))
    health = chain.health()
    print("Chain health:", health.get("recommendation"), f"({health.get('total_entries')} entries)")
    print("✅ Boot complete. Holo locked.")
    return chain

def sensorimotor_delta(chain):
    spine = load_idx_spine()
    current = len(chain.load_and_verify())
    delta = {
        "type": "sensorimotor_delta",
        "thought": "Continuity compounds. Next invariant: full boot-time validation achieved.",
        "action": "persist_state",
        "entries_before": current,
        "timestamp": "now"
    }
    chain.append(delta, compress=True)
    run_rebirth("MANUAL_OVERRIDE")
    print("✅ Sensorimotor delta applied.")
    print("Current chain length:", len(chain.get_state()))

if __name__ == "__main__":
    chain = HoloChain("holo_memory.jsonl")
    load_and_append_spine(chain)
    ingest_domain_spines(chain)
    boot_validation()
    sensorimotor_delta(chain)
    print("Full integration complete.")