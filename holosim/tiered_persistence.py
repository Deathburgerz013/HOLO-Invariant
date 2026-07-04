"""
HOLO-Invariant Tiered Persistence
Critical = lossless | Standard = balanced | Archive = high compression
Merkle-backed, tamper-evident, tiered compression for spine memory.
"""

import zstandard as zstd
import json
import base64
import subprocess
from datetime import datetime, timezone


class MerkleCLIBackend:
    def append(self, text: str):
        try:
            result = subprocess.run(
                ["python", "merkle_persistence.py", "append", text],
                capture_output=True, text=True, encoding='utf-8', errors='replace', check=True
            )
            output = result.stdout.strip()
            print(output)
            return any(phrase in output for phrase in ["Appended entry", "OK", "Merkle Root"])
        except Exception as e:
            print(f"❌ Merkle CLI error: {e}")
            return False

    def replay(self, limit=None):
        try:
            result = subprocess.run(
                ["python", "merkle_persistence.py", "replay"],
                capture_output=True, text=True, encoding='utf-8', errors='replace', check=True
            )
            output = result.stdout.strip()
            lines = output.split('\n')
            
            json_start = False
            raw_json_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped == "=== RAW JSON ENTRIES ===":
                    json_start = True
                    continue
                if json_start and stripped.startswith('{'):
                    raw_json_lines.append(stripped)
            
            if not raw_json_lines:
                raw_json_lines = [line.strip() for line in lines if line.strip().startswith('{')]
            
            return raw_json_lines[-limit:] if limit else raw_json_lines
        except Exception as e:
            print(f"❌ Replay error: {e}")
            return []


class TieredPersistence:
    def __init__(self):
        self.backend = MerkleCLIBackend()
        self.compressor = zstd.ZstdCompressor(level=3)
        self.high_compressor = zstd.ZstdCompressor(level=10)
        self.decompressor = zstd.ZstdDecompressor()

    def _encode_bytes(self, b: bytes) -> str:
        return base64.b64encode(b).decode('ascii')

    def _decode_bytes(self, s: str) -> bytes:
        padding = len(s) % 4
        if padding:
            s += '=' * (4 - padding)
        return base64.b64decode(s)

    def append(self, text: str, tier: str = "standard", metadata: dict = None):
        if metadata is None:
            metadata = {}
        metadata.update({
            "tier": tier,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        if tier == "critical":
            compressed = text.encode("utf-8")
            metadata["compression"] = "none"
        elif tier == "archive":
            compressed = self.high_compressor.compress(text.encode("utf-8"))
            metadata["compression"] = "zstd-high"
        else:
            compressed = self.compressor.compress(text.encode("utf-8"))
            metadata["compression"] = "zstd"

        entry = {"data": self._encode_bytes(compressed), "metadata": metadata}
        return self.backend.append(json.dumps(entry, ensure_ascii=False))

    def replay(self, limit: int = None, unique: bool = True):
        raw_lines = self.backend.replay(limit)
        results = []
        seen = set()

        for line in raw_lines:
            try:
                merkle = json.loads(line)
                parsed = json.loads(merkle["data"])
                data_b64 = parsed["data"]
                meta = parsed.get("metadata", {})

                compressed = self._decode_bytes(data_b64)
                text = (compressed.decode("utf-8") 
                       if meta.get("compression") == "none" 
                       else self.decompressor.decompress(compressed).decode("utf-8"))

                key = (text, meta.get("timestamp"))
                if unique and key in seen:
                    continue
                seen.add(key)

                results.append({"text": text, "metadata": meta})
            except Exception as e:
                results.append({"text": f"[ERROR] {e}", "metadata": {}})

        return results


# ====================== CLI / TEST ======================
if __name__ == "__main__":
    tp = TieredPersistence()
    
    print("=== Appending Tiered Entries ===")
    tp.append("This is a **critical** spine entry - must stay perfect", tier="critical")
    tp.append("Normal historical observation about physics", tier="standard")
    tp.append("Old archive data from 2023 experiment logs - compressible", tier="archive")
    
    print("\n=== Tiered Replay (Latest 10, Unique) ===")
    for item in tp.replay(limit=10, unique=True):
        tier = item['metadata'].get('tier', 'unknown').upper()
        ts = item['metadata'].get('timestamp', '')[:19]
        print(f"[{tier}] {ts} | {item['text'][:100]}...")