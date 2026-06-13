import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

class HoloChain:
    def __init__(self, file_path: str = "holo_memory.jsonl", genesis_hash: str = "0" * 64):
        self.file_path = Path(file_path)
        self.genesis_hash = genesis_hash
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, prev_hash: str, content: str, timestamp: str, idx: int) -> str:
        canonical = json.dumps({
            "idx": idx,
            "timestamp": timestamp,
            "content": content
        }, separators=(',', ':'), sort_keys=True)
        data = prev_hash.encode() + canonical.encode()
        return hashlib.sha256(data).hexdigest()

    def load_and_verify(self) -> List[Dict]:
        if not self.file_path.exists():
            return []
        entries = []
        prev_hash = self.genesis_hash
        with self.file_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line: continue
                entry = json.loads(line)
                expected = self._compute_hash(prev_hash, entry["content"], entry["timestamp"], entry["idx"])
                if entry["hash"] != expected or ("prev_hash" in entry and entry["prev_hash"] != prev_hash):
                    raise ValueError(f"Integrity failure at line {line_num}")
                prev_hash = entry["hash"]
                entries.append(entry)
        # Monotonic index check omitted for minimal form
        return entries

    def append(self, content: Any) -> Dict:
        entries = self.load_and_verify()
        idx = len(entries) + 1
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        prev_hash = self.genesis_hash if not entries else entries[-1]["hash"]
        if isinstance(content, (dict, list)):
            content = json.dumps(content, separators=(',', ':'), sort_keys=True)
        entry_hash = self._compute_hash(prev_hash, content, timestamp, idx)
        entry = {
            "idx": idx,
            "timestamp": timestamp,
            "content": content,
            "prev_hash": prev_hash,
            "hash": entry_hash
        }
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

if __name__ == "__main__":
    import sys
    chain = HoloChain("holo_memory.jsonl")
   
    if len(sys.argv) > 1 and sys.argv[1] == "append":
        content = " ".join(sys.argv[2:])
        entry = chain.append(content)
        print(f"Appended entry #{entry['idx']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "verify":
        loaded = chain.load_and_verify()
        print(f"Verified {len(loaded)} entries. Chain intact.")
    else:
        print("Usage: python holo_chain.py append \"your message\"")
        print("       python holo_chain.py verify")