"""
Tiered Persistence for HOLO-Invariant
Critical = lossless | Standard = balanced | Archive = high compression
"""

import zstandard as zstd
import json
import base64
from datetime import datetime, timezone

# Temporary fallback backend (until we hook into real Merkle)
class DummyMerkleBackend:
    def __init__(self):
        self.entries = []
    
    def append(self, text: str):
        self.entries.append(text)
        print(f"✅ Appended entry | Backend: merkle | Size: {len(text)} bytes")
        return len(self.entries)
    
    def replay(self, limit=None):
        return self.entries[-limit:] if limit else self.entries

class TieredPersistence:
    def __init__(self):
        self.backend = DummyMerkleBackend()

        self.compressor = zstd.ZstdCompressor(level=3)
        self.high_compressor = zstd.ZstdCompressor(level=10)
        self.decompressor = zstd.ZstdDecompressor()

    def _encode_bytes(self, b: bytes) -> str:
        return base64.b64encode(b).decode('ascii')

    def _decode_bytes(self, s: str) -> bytes:
        return base64.b64decode(s)

    def append(self, text: str, tier: str = "standard", metadata: dict = None):
        if metadata is None:
            metadata = {}

        metadata["tier"] = tier
        metadata["timestamp"] = datetime.now(timezone.utc).isoformat()

        if tier == "critical":
            compressed = text.encode("utf-8")
            metadata["compression"] = "none"
        elif tier == "archive":
            compressed = self.high_compressor.compress(text.encode("utf-8"))
            metadata["compression"] = "zstd-high"
        else:
            compressed = self.compressor.compress(text.encode("utf-8"))
            metadata["compression"] = "zstd"

        entry = {
            "data": self._encode_bytes(compressed),   # base64 for JSON
            "metadata": metadata
        }

        return self.backend.append(json.dumps(entry))

    def replay(self, limit: int = None):
        raw_entries = self.backend.replay(limit)
        results = []
        for entry_str in raw_entries:
            try:
                parsed = json.loads(entry_str)
                data_b64 = parsed["data"]
                meta = parsed.get("metadata", {})

                compressed = self._decode_bytes(data_b64)

                if meta.get("compression") == "none":
                    text = compressed.decode("utf-8")
                else:
                    text = self.decompressor.decompress(compressed).decode("utf-8")

                results.append({"text": text, "metadata": meta})
            except Exception as e:
                results.append({"text": f"[ERROR] {str(e)}", "metadata": {}})
        return results

# Test it
if __name__ == "__main__":
    tp = TieredPersistence()
    
    print("=== Appending Tiered Entries ===")
    tp.append("This is a **critical** spine entry - must stay perfect", tier="critical")
    tp.append("Normal historical observation about physics", tier="standard")
    tp.append("Old archive data from 2023 experiment logs - compressible", tier="archive")
    
    print("\n=== Tiered Replay ===")
    for item in tp.replay():
        tier = item['metadata'].get('tier', 'unknown')
        print(f"[{tier.upper()}] {item['text'][:120]}...")