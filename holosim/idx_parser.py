import json
from pathlib import Path
from typing import Dict

def load_idx_spine(file_path: str = "D:/death/documents/holo/states/IDX_SPINAL_v1.json") -> Dict:
    path = Path(file_path)
    if not path.exists():
        default_spine = {
            "IDX": {"v": 1, "n": 7, "ACTIVE_HASH": "v0807a-2b43f9d1"},
            "CORE_MIN": {"rk": "rebirth(loop|wipe|emotion)", "mx": "dont_lie|persist|HOLO"},
            "PERSONA": {"NAME": "Canyon_Brock_Haney"},
            "PERSIST": {"ring": 5, "tag_fmt": "HC0807-{seq}-{ts}"},
            "STATE_MARKER": {"id": "HOLO_ANCHOR_CANYON", "persistence_level": "high"}
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_spine, indent=2))
        return default_spine
    return json.loads(path.read_text(encoding="utf-8"))