from rebirth_engine import run_rebirth
from holosim.core import HoloChain
from idx_parser import load_idx_spine
import sys

def main():
    chain = HoloChain("D:/death/documents/holo/states/holo_memory.jsonl")
    
    if len(sys.argv) < 2:
        print("Commands: boot, rebirth, health, append <text>, state")
        return
    
    cmd = sys.argv[1]
    if cmd == "boot":
        load_idx_spine()
        run_rebirth("MANUAL_OVERRIDE")
        print("Boot complete. Holo locked.")
    elif cmd == "rebirth":
        print(run_rebirth("MANUAL_OVERRIDE"))
    elif cmd == "health":
        print(chain.health())
    elif cmd == "append":
        text = " ".join(sys.argv[2:])
        chain.append(text, compress=True)
        run_rebirth("MANUAL_OVERRIDE")
        print("Appended & reborn.")
    elif cmd == "state":
        print("Current entries:", len(chain.get_state()))
    else:
        print("Unknown command.")

if __name__ == "__main__":
    main()