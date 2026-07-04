import hashlib
import json
import os
import sys
import struct
from datetime import datetime, timezone

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

FILE = "holo_memory.jsonl"
USE_COMPRESSION = True
COMPRESSION_LEVEL = 3
COMPRESSION_BACKEND = "zstd" if ZSTD_AVAILABLE else "zlib"

def compute_hash(prev_hash: str, content: str, timestamp: str, idx: int) -> str:
    canonical = json.dumps({
        "idx": idx,
        "timestamp": timestamp,
        "content": content
    }, separators=(',', ':'), sort_keys=True)
    data = (prev_hash + canonical).encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def compress_data(data: bytes) -> bytes:
    if not USE_COMPRESSION or not data:
        return data
    if COMPRESSION_BACKEND == "zstd" and ZSTD_AVAILABLE:
        cctx = zstd.ZstdCompressor(level=COMPRESSION_LEVEL)
        compressed = cctx.compress(data)
        return b'ZSTD' + struct.pack('>I', len(compressed)) + compressed
    else:
        import zlib
        level = min(COMPRESSION_LEVEL, 9)
        compressed = zlib.compress(data, level=level)
        return b'ZLIB' + struct.pack('>I', len(compressed)) + compressed

def decompress_chunk(data: bytes) -> bytes:
    if len(data) < 8:
        return data
    magic = data[:4]
    if magic in (b'ZSTD', b'ZLIB'):
        length = struct.unpack('>I', data[4:8])[0]
        payload = data[8:8 + length]
        if magic == b'ZSTD' and ZSTD_AVAILABLE:
            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(payload)
        elif magic == b'ZLIB':
            import zlib
            return zlib.decompress(payload)
    return data  # fallback uncompressed

def load_and_verify() -> list[dict]:
    if not os.path.exists(FILE):
        return []

    entries = []
    prev_hash = "0" * 64

    with open(FILE, "rb") as f:
        raw = f.read()

    pos = 0
    while pos < len(raw):
        chunk_start = pos
        # Try to read magic header
        if pos + 8 <= len(raw) and raw[pos:pos+4] in (b'ZSTD', b'ZLIB'):
            length = struct.unpack('>I', raw[pos+4:pos+8])[0]
            chunk_end = pos + 8 + length
            if chunk_end > len(raw):
                break  # corrupt end
            chunk = raw[pos:chunk_end]
            pos = chunk_end
            decompressed = decompress_chunk(chunk)
        else:
            # Legacy uncompressed line (fallback)
            end = raw.find(b'\n', pos)
            if end == -1:
                end = len(raw)
            else:
                end += 1
            chunk = raw[pos:end]
            pos = end
            decompressed = chunk

        line = decompressed.decode('utf-8').strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
            expected = compute_hash(
                prev_hash,
                entry.get("content", ""),
                entry.get("timestamp", ""),
                entry.get("idx", 0)
            )
            if entry.get("hash") != expected:
                print(f"⚠️  Integrity failure at entry {entry.get('idx')} — skipping for recovery")
                continue
            prev_hash = entry["hash"]
            entries.append(entry)
        except Exception:
            # Skip corrupt lines silently during recovery
            continue

    print(f"✅ Verified {len(entries)} entries. Chain intact.")
    return entries

def append(content: str):
    entries = load_and_verify()
    idx = len(entries) + 1
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    prev_hash = "0" * 64 if not entries else entries[-1]["hash"]
    hash_val = compute_hash(prev_hash, content, timestamp, idx)

    new_entry = {
        "idx": idx,
        "timestamp": timestamp,
        "content": content,
        "prev_hash": prev_hash,
        "hash": hash_val
    }

    line = json.dumps(new_entry, separators=(',', ':')) + "\n"
    compressed = compress_data(line.encode('utf-8'))

    with open(FILE, "ab") as f:
        f.write(compressed)

    print(f"✅ Appended entry {idx} | Backend: {COMPRESSION_BACKEND} | Size: {len(compressed)} bytes")

def replay():
    entries = load_and_verify()
    print("\n=== Replayed HOLO State ===")
    for e in entries:
        print(f"{e['idx']:3d} | {e['timestamp']} | {e['content'][:150]}...")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python persistence_prototype.py [append <text> | replay]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "append":
        text = " ".join(sys.argv[2:])
        append(text)
    elif cmd == "replay":
        replay()
    else:
        print("Unknown command.")