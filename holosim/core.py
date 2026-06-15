import hashlib
import json
import logging
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HoloChain:
    """Tamper-evident append-only chain for AI continuity and long-term memory."""

    def __init__(self, file_path: str = "holo_memory.jsonl", genesis_hash: str = "0" * 64):
        self.file_path = Path(file_path)
        self.genesis_hash = genesis_hash
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, prev_hash: str, content: str, timestamp: str, idx: int) -> str:
        """Deterministic canonical hash."""
        canonical = json.dumps({
            "idx": idx,
            "timestamp": timestamp,
            "content": content
        }, separators=(',', ':'), sort_keys=True)
        data = prev_hash.encode() + canonical.encode()
        return hashlib.sha256(data).hexdigest()

    def load_and_verify(self) -> List[Dict]:
        """Load and fully verify the entire chain. Fails fast on tampering."""
        if not self.file_path.exists():
            return []
        entries = []
        prev_hash = self.genesis_hash
        with self.file_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    expected = self._compute_hash(
                        prev_hash, entry["content"], entry["timestamp"], entry["idx"]
                    )
                    if entry["hash"] != expected:
                        raise ValueError(f"Hash mismatch at line {line_num}")
                    if entry.get("prev_hash") != prev_hash:
                        raise ValueError(f"Prev hash mismatch at line {line_num}")
                    prev_hash = entry["hash"]
                    entries.append(entry)
                except Exception as e:
                    logger.error(f"Integrity failure at line {line_num}: {e}")
                    raise
        # Monotonic index check
        for i, e in enumerate(entries):
            if e["idx"] != i + 1:
                raise ValueError("Index not monotonic")
        logger.info(f"✅ Verified {len(entries)} entries. Chain intact.")
        return entries

    def append(self, content: Any, compress: bool = False) -> Dict:
        """Append new entry. Optional compression for density."""
        entries = self.load_and_verify()
        idx = len(entries) + 1
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        prev_hash = self.genesis_hash if not entries else entries[-1]["hash"]

        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False)
        elif not isinstance(content, str):
            content = str(content)

        # Optional compression
        if compress:
            compressed = zlib.compress(content.encode('utf-8'))
            content = compressed.hex()  # Store as hex string
            entry_type = "compressed"
        else:
            entry_type = "plain"

        hash_val = self._compute_hash(prev_hash, content, timestamp, idx)

        entry = {
            "idx": idx,
            "timestamp": timestamp,
            "content": content,
            "prev_hash": prev_hash,
            "hash": hash_val,
            "type": entry_type  # metadata for future decompression
        }

        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"✅ Appended entry {idx} ({entry_type})")
        return entry

    def replay(self) -> List[Dict]:
        """Replay full history."""
        entries = self.load_and_verify()
        print("\n=== HOLO-CHAIN REPLAY ===")
        for e in entries:
            snippet = e['content'][:120] + ('...' if len(e['content']) > 120 else '')
            ctype = e.get('type', 'plain')
            print(f"{e['idx']:3} | {e['timestamp']} | [{ctype}] {snippet}")
        return entries

    def get_state(self) -> List[Any]:
        """Reconstruct current state (decompress if needed)."""
        entries = self.load_and_verify()
        state = []
        for e in entries:
            content = e["content"]
            if e.get("type") == "compressed":
                try:
                    content = zlib.decompress(bytes.fromhex(content)).decode('utf-8')
                except Exception:
                    content = f"[DECOMPRESSION FAILED] {content[:100]}..."
            if content.startswith(('{', '[')):
                try:
                    state.append(json.loads(content))
                except:
                    state.append(content)
            else:
                state.append(content)
        return state

    def get_density_stats(self) -> Dict:
        """Return compression/density statistics."""
        entries = self.load_and_verify()
        total_original = 0
        total_stored = 0
        compressed_count = 0

        for e in entries:
            stored_len = len(e["content"])
            total_stored += stored_len
            if e.get("type") == "compressed":
                compressed_count += 1
                # Rough original estimate not stored - we can improve later
            else:
                total_original += stored_len

        return {
            "total_entries": len(entries),
            "compressed_entries": compressed_count,
            "total_stored_bytes": total_stored,
            "compression_ratio": round(total_stored / max(total_original, 1), 3) if total_original else 0
        }