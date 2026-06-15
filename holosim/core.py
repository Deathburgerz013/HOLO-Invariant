import hashlib
import json
import logging
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HoloChain:
    """Tamper-evident append-only chain for AI/human continuity and long-term memory (HSSCE primitive).

    Core invariants:
    - Cryptographically verifiable (SHA-256 + canonical JSON).
    - Append-only, fails-fast on tampering (strict mode default).
    - Optional smart compression for density/scalability.
    - Fully reproducible across time and systems.
    - Auditable with clear original_size tracking.
    """

    VERSION = "0.4.5"  # Convergence update - merged threads

    def __init__(self, file_path: str = "holo_memory.jsonl", genesis_hash: str = "0" * 64):
        self.file_path = Path(file_path)
        self.genesis_hash = genesis_hash
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, prev_hash: str, content: str, timestamp: str, idx: int) -> str:
        """Deterministic canonical hash for tamper-evidence."""
        canonical = json.dumps({
            "idx": idx,
            "timestamp": timestamp,
            "content": content
        }, separators=(',', ':'), sort_keys=True)
        data = prev_hash.encode() + canonical.encode()
        return hashlib.sha256(data).hexdigest()

    def load_and_verify(self, strict: bool = True) -> List[Dict]:
        """Load and fully verify the entire chain. Fails fast on tampering by default."""
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
                        prev_hash, entry.get("content", ""), entry.get("timestamp", ""), entry.get("idx", 0)
                    )
                    if entry.get("hash") != expected:
                        msg = f"Hash mismatch at line {line_num}"
                        if strict:
                            raise ValueError(msg)
                        logger.warning(msg)
                    if entry.get("prev_hash") != prev_hash:
                        msg = f"Prev hash mismatch at line {line_num}"
                        if strict:
                            raise ValueError(msg)
                        logger.warning(msg)
                    prev_hash = entry.get("hash")
                    entries.append(entry)
                except Exception as e:
                    logger.error(f"Integrity failure at line {line_num}: {e}")
                    if strict:
                        raise
                    # Non-strict: continue with warning for resilience
        # Monotonic index check
        for i, e in enumerate(entries):
            if e.get("idx") != i + 1:
                msg = f"Index not monotonic at entry {i+1}"
                if strict:
                    raise ValueError(msg)
                logger.warning(msg)
        logger.info(f"✅ Verified {len(entries)} entries. Chain intact. [HoloChain v{self.VERSION}]")
        return entries

    def append(self, content: Any, compress: bool = False, min_compress_size: int = 128) -> Dict:
        """Append new entry with smart optional compression for density."""
        entries = self.load_and_verify()
        idx = len(entries) + 1
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        prev_hash = self.genesis_hash if not entries else entries[-1].get("hash")

        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, ensure_ascii=False)
        elif not isinstance(content, str):
            content_str = str(content)
        else:
            content_str = content

        original_content = content_str
        entry_type = "plain"

        # Smart compression
        if compress and len(original_content) >= min_compress_size:
            compressed = zlib.compress(original_content.encode('utf-8'))
            compressed_hex = compressed.hex()
            if len(compressed_hex) < len(original_content):
                content_str = compressed_hex
                entry_type = "compressed"

        hash_val = self._compute_hash(prev_hash, content_str, timestamp, idx)

        entry = {
            "idx": idx,
            "timestamp": timestamp,
            "content": content_str,
            "prev_hash": prev_hash,
            "hash": hash_val,
            "type": entry_type,
            "original_size": len(original_content)  # Accurate density tracking
        }

        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"✅ Appended entry {idx} ({entry_type}) [HoloChain v{self.VERSION}]")
        return entry

    def replay(self, full: bool = False) -> List[Dict]:
        """Replay full history. Use full=True for complete content."""
        entries = self.load_and_verify()
        print("\n=== HOLO-CHAIN REPLAY ===")
        for e in entries:
            snippet = e.get('content', '')
            if not full:
                snippet = snippet[:120] + ('...' if len(snippet) > 120 else '')
            ctype = e.get('type', 'plain')
            print(f"{e.get('idx', '?'):3} | {e.get('timestamp', '?')} | [{ctype}] {snippet}")
        return entries

    def get_state(self) -> List[Any]:
        """Reconstruct current state (decompress if needed)."""
        entries = self.load_and_verify()
        state = []
        for e in entries:
            content = e.get("content", "")
            if e.get("type") == "compressed":
                try:
                    content = zlib.decompress(bytes.fromhex(content)).decode('utf-8')
                except Exception:
                    content = f"[DECOMPRESSION FAILED] {content[:100]}..."
            try:
                if content.startswith(('{', '[')):
                    state.append(json.loads(content))
                else:
                    state.append(content)
            except Exception:
                state.append(content)
        return state

    def get_density_stats(self) -> Dict:
        """Return compression/density statistics with accurate original size tracking."""
        entries = self.load_and_verify()
        total_original = 0
        total_stored = 0
        compressed_count = 0
        plain_count = 0
        for e in entries:
            stored_len = len(e.get("content", ""))
            total_stored += stored_len
            if e.get("type") == "compressed":
                compressed_count += 1
                original_len = e.get("original_size", stored_len)
                total_original += original_len
            else:
                plain_count += 1
                total_original += stored_len

        total_entries = len(entries)
        overall_ratio = round(total_stored / max(total_original, 1), 4) if total_original else 0
        return {
            "total_entries": total_entries,
            "plain_entries": plain_count,
            "compressed_entries": compressed_count,
            "total_original_bytes": total_original,
            "total_stored_bytes": total_stored,
            "compression_ratio": overall_ratio,
            "compression_savings_percent": round((1 - overall_ratio) * 100, 2) if total_original else 0,
            "version": self.VERSION
        }

    def get_entries_since(self, timestamp: str) -> List[Dict]:
        """Query entries after a given timestamp (ISO format)."""
        entries = self.load_and_verify()
        return [e for e in entries if e.get("timestamp", "") > timestamp]

    def search_content(self, pattern: str, case_sensitive: bool = False) -> List[Dict]:
        """Simple content search across entries."""
        entries = self.load_and_verify()
        if not case_sensitive:
            pattern = pattern.lower()
        results = []
        for e in entries:
            content = str(e.get("content", ""))
            content_check = content.lower() if not case_sensitive else content
            if pattern in content_check:
                results.append(e)
        return results

    def print_state(self):
        """Nice formatted state output for CLI / debugging."""
        state = self.get_state()
        print("\n=== CURRENT HOLO STATE ===")
        print(f"Total entries: {len(state)}\n")
        for i, item in enumerate(state, 1):
            if isinstance(item, dict):
                print(f"{i:3}. {json.dumps(item, ensure_ascii=False, indent=2)}")
            elif isinstance(item, str):
                print(f"{i:3}. {item}")
            else:
                print(f"{i:3}. {repr(item)}")
        print("\n=== END STATE ===\n")

    def get_latest(self) -> Optional[Dict]:
        """Convenience: return most recent entry (verified)."""
        entries = self.load_and_verify()
        return entries[-1] if entries else None