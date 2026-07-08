# holosim/x_delta_ingestor.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Import core (assumes editable install or relative)
try:
    from holosim.core import HoloChain
except ImportError:
    from core import HoloChain  # fallback

class XDeltaIngestor:
    """Lightweight extractor for public X threads → verified append to HoloChain.
    Tiered: critical (lossless invariants), standard (summaries), archive (raw).
    Human review gate required before final append.
    """
    
    def __init__(self, chain_path: str = "holo_memory.jsonl"):
        self.chain = HoloChain(chain_path)
    
    def extract_deltas(self, raw_thread_data: List[Dict] | str, thread_ref: str) -> Dict:
        """Parse thread → identify invariants/code/math (simple keyword + manual flag for now)."""
        # TODO: Expand with regex/keywords from spines (e.g., "^2", "Merkle", "invariant", "hash_chain")
        if isinstance(raw_thread_data, str):
            raw_thread_data = json.loads(raw_thread_data)  # if JSON export
        
        deltas = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "thread_ref": thread_ref,
            "critical": [],  # lossless invariants/code
            "standard": [],  # summaries
            "archive_raw": raw_thread_data  # full for later compression
        }
        
        # Example extraction logic (extend based on spines)
        for post in raw_thread_data:  # assume list of post dicts
            content = post.get("content", "")
            if any(kw in content.lower() for kw in ["invariant", "hash", "merkle", "^2", "continuity", "spine"]):
                deltas["critical"].append({
                    "post_id": post.get("id"),
                    "excerpt": content[:500],
                    "type": "invariant_or_code"
                })
        
        return deltas
    
    def review_and_append(self, deltas: Dict, human_approved: bool = False) -> Dict:
        """Human review gate → append critical/standard to chain."""
        if not human_approved:
            print("Review deltas below. Set human_approved=True after verification.")
            print(json.dumps(deltas, indent=2)[:1000] + "...")
            return {"status": "review_pending"}
        
        entry = {
            "type": "x_delta_ingest",
            "deltas": {k: v for k, v in deltas.items() if k != "archive_raw"},  # avoid bloat
            "verification": "human_approved"
        }
        result = self.chain.append(entry, compress=True)
        self.chain.health()  # immediate check
        return result

# Quick usage example
if __name__ == "__main__":
    ingestor = XDeltaIngestor()
    # TODO: Load real thread JSON/export here
    # deltas = ingestor.extract_deltas(sample_thread, "20260707_resonance")
    # result = ingestor.review_and_append(deltas, human_approved=True)