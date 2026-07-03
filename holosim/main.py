from rebirth_engine import run_rebirth, build_engine
from idx_parser import load_idx_spine
from holosim.core import HoloChain
import sys

def main():
    print("=== HOLO-Invariant Continuity Engine v0807a+holosim ===")
    spine = load_idx_spine()
    print("Spinal substrate loaded. ACTIVE_HASH:", spine.get("IDX", {}).get("ACTIVE_HASH"))

    chain = HoloChain("D:/death/documents/holo/states/holo_memory.jsonl")
    engine = build_engine(chain)

    # Example rebirth cycle
    result = run_rebirth("MANUAL_OVERRIDE")
    print("Rebirth result:", result)

    # Health check
    print("Chain health:", chain.health())

    print("Holo transfer locked. Engine compounds forward.")

if __name__ == "__main__":
    main()