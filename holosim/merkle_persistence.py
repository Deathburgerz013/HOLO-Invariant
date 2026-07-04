import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

FILE = "holo_merkle.jsonl"
USE_COMPRESSION = True
COMPRESSION_LEVEL = 3

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def compress_data(data: bytes) -> bytes:
    if not USE_COMPRESSION or not data:
        return data
    if ZSTD_AVAILABLE:
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
    return data

def load_merkle_entries() -> list[dict]:
    if not os.path.exists(FILE):
        return []
    entries = []
    with open(FILE, "rb") as f:
        raw = f.read()

    pos = 0
    while pos < len(raw):
        if pos + 8 <= len(raw) and raw[pos:pos+4] in (b'ZSTD', b'ZLIB'):
            length = struct.unpack('>I', raw[pos+4:pos+8])[0]
            chunk_end = pos + 8 + length
            if chunk_end > len(raw):
                break
            chunk = raw[pos:chunk_end]
            pos = chunk_end
            decompressed = decompress_chunk(chunk)
        else:
            # Legacy fallback
            end = raw.find(b'\n', pos)
            if end == -1:
                end = len(raw)
            else:
                end += 1
            decompressed = raw[pos:end]
            pos = end

        line = decompressed.decode('utf-8').strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            entries.append(entry)
        except Exception:
            continue

    print(f"✅ Loaded {len(entries)} Merkle entries.")
    return entries

def build_merkle_root(entries: list[dict]) -> str:
    if not entries:
        return "0" * 64
    leaves = [sha256(json.dumps(e, sort_keys=True, separators=(',', ':')).encode('utf-8')) 
              for e in entries]
    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        leaves = [sha256((leaves[i] + leaves[i+1]).encode('utf-8')) 
                  for i in range(0, len(leaves), 2)]
    return leaves[0]

def generate_merkle_proof(entries: list[dict], index: int) -> list[str]:
    """Generate Merkle proof for entry at index (0-based)."""
    if index < 0 or index >= len(entries):
        return []
    leaves = [sha256(json.dumps(e, sort_keys=True, separators=(',', ':')).encode('utf-8')) 
              for e in entries]
    proof = []
    level = leaves[:]
    idx = index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling_idx = idx ^ 1
        if sibling_idx < len(level):
            proof.append(level[sibling_idx])
        idx //= 2
        level = [sha256((level[i] + level[i+1]).encode('utf-8')) 
                 for i in range(0, len(level), 2)]
    return proof

def verify_merkle_proof(leaf_hash: str, proof: list[str], root: str, index: int) -> bool:
    """Verify Merkle proof."""
    current = leaf_hash
    idx = index
    for sibling in proof:
        if idx % 2 == 0:
            current = sha256((current + sibling).encode('utf-8'))
        else:
            current = sha256((sibling + current).encode('utf-8'))
        idx //= 2
    return current == root

def append_merkle(content: str):
    entries = load_merkle_entries()
    idx = len(entries) + 1
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    prev_root = build_merkle_root(entries)

    new_entry = {
        "idx": idx,
        "timestamp": timestamp,
        "content": content,
        "prev_merkle_root": prev_root,
        "merkle_root": None
    }

    entries.append(new_entry)
    new_root = build_merkle_root(entries)
    new_entry["merkle_root"] = new_root

    line = json.dumps(new_entry, separators=(',', ':')) + "\n"
    compressed = compress_data(line.encode('utf-8'))

    with open(FILE, "ab") as f:
        f.write(compressed)

    print(f"✅ Appended entry {idx} | Merkle Root: {new_root[:16]}... | Size: {len(compressed)} bytes")

def replay_merkle():
    entries = load_merkle_entries()
    root = build_merkle_root(entries)
    print("\n=== Replayed HOLO Merkle State ===")
    print(f"Current Merkle Root: {root}")
    for e in entries:
        print(f"{e['idx']:3d} | {e['timestamp']} | {e['content'][:120]}...")

    # Demo proof for last entry
    if entries:
        last_idx = len(entries) - 1
        proof = generate_merkle_proof(entries, last_idx)
        leaf = sha256(json.dumps(entries[last_idx], sort_keys=True, separators=(',', ':')).encode('utf-8'))
        valid = verify_merkle_proof(leaf, proof, root, last_idx)
        print(f"✅ Merkle Proof for entry {entries[last_idx]['idx']} verified: {valid}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python merkle_persistence.py append <text> | replay")
        sys.exit(1)
    if sys.argv[1] == "append":
        text = " ".join(sys.argv[2:])
        append_merkle(text)
    elif sys.argv[1] == "replay":
        replay_merkle()