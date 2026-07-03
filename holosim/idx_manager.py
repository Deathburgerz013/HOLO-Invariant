from rebirth_engine import run_rebirth
from holosim.core import HoloChain
from idx_parser import load_idx_spine   # <-- This was missing
import json
from pathlib import Path

def load_and_append_spine(chain: HoloChain, idx_path: str = "D:/death/documents/holo/states/IDX_SPINAL_v1.json"):
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
    run_rebirth("MANUAL_OVERRIDE")  # Ensure rebirth after spine update
    return chain.get_state()

# Run once
if __name__ == "__main__":
    chain = HoloChain("D:/death/documents/holo/states/holo_memory.jsonl")
    load_and_append_spine(chain)

def ingest_domain_spines(chain: HoloChain, spines_dir: str = "D:/death/Holo-Invariant-main"):
    """Ingest clean domain spines as invariants."""
    important_spines = ["Physics_Spine.md", "Biology_Spine.md", "Computation_Systems_Spine.md", "Mathematics_Spine.md"]
    for name in important_spines:
        path = Path(spines_dir) / name
        if path.exists():
            content = path.read_text(encoding="utf-8")[:2000]  # truncate for density
            payload = {"type": "domain_spine", "name": name, "content": content, "action": "invariant_ingested"}
            chain.append(payload, compress=True)
            print(f"✅ Ingested {name}")
    run_rebirth("MANUAL_OVERRIDE")
    print("Domain spines fused.")

# Run this next
if __name__ == "__main__":
    chain = HoloChain("D:/death/documents/holo/states/holo_memory.jsonl")
    ingest_domain_spines(chain)

from rebirth_engine import run_rebirth
from holosim.core import HoloChain
from idx_parser import load_idx_spine
from pathlib import Path

def boot_validation():
    print("=== HOLO Engine Boot Validation ===")
    chain = HoloChain("D:/death/documents/holo/states/holo_memory.jsonl")
    
    # Load & verify spine
    spine = load_idx_spine()
    print(f"Spine version: v{spine.get('IDX', {}).get('v')} | Hash: {spine.get('IDX', {}).get('ACTIVE_HASH')}")
    
    # Rebirth + health
    result = run_rebirth("MANUAL_OVERRIDE")
    print("Rebirth:", result["status"])
    
    health = chain.health()
    print("Chain health:", health["recommendation"], f"({health['total_entries']} entries)")
    
    print("Boot complete. Holo locked.")
    return chain

if __name__ == "__main__":
    boot_validation()

from rebirth_engine import run_rebirth
from holosim.core import HoloChain
from idx_parser import load_idx_spine

def sensorimotor_delta(chain):
    """Minimal: read spine → compute simple delta → append action."""
    spine = load_idx_spine()
    current_entries = len(chain.load_and_verify()) if hasattr(chain, 'load_and_verify') else 0
    
    delta = {
        "type": "sensorimotor_delta",
        "thought": "Continuity compounds. Next invariant: full boot-time validation achieved.",
        "action": "persist_state",
        "entries_before": current_entries,
        "timestamp": "now"
    }
    
    chain.append(delta, compress=True)
    run_rebirth("MANUAL_OVERRIDE")
    print("✅ Sensorimotor delta applied and persisted.")
    print("Current chain length:", len(chain.get_state()))

if __name__ == "__main__":
    chain = HoloChain("D:/death/documents/holo/states/holo_memory.jsonl")
    sensorimotor_delta(chain)