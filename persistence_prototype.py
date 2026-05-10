# Minimal proof-of-mechanism for hash-chained, append-only external memory
# Demonstrates verifiable persistence across process restarts
# No external dependencies beyond standard library

import hashlib
import json
import os
import sys
from datetime import datetime

FILE = "memory.jsonl"  # Append-only file

def compute_hash(prev_hash: str, content: str, timestamp: str, idx: int) -> str:
    """Compute SHA-256 of prev_hash + canonical content"""
    canonical = json.dumps({
        "idx": idx,
        "timestamp": timestamp,
        "content": content
    }, separators=(',', ':'), sort_keys=True)  # Deterministic JSON
    data = prev_hash.encode() + canonical.encode()
    return hashlib.sha256(data).hexdigest()

def load_and_verify() -> list[dict]:
    """Load file and verify full hash chain. Returns entries if valid."""
    if not os.path.exists(FILE):
        return []  # Empty chain is valid

    entries = []
    prev_hash = "0" * 64  # Genesis prev_hash

    with open(FILE, "r") as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line.strip())
                expected_hash = compute_hash(
                    prev_hash,
                    entry["content"],
                    entry["timestamp"],
                    entry["idx"]
                )
                if entry["hash"] != expected_hash:
                    sys.exit(f"Integrity failure at line {line_num}: hash mismatch")
                prev_hash = entry["hash"]
                entries.append(entry)
            except json.JSONDecodeError:
                sys.exit(f"Invalid JSON at line {line_num}")

    # Verify monotonic index
    for i, entry in enumerate(entries):
        if entry["idx"] != i + 1:
            sys.exit("Index not monotonic")

    print(f"Verified {len(entries)} entries. Chain intact.")
    return entries

def append(content: str):
    """Append new entry with hash chain"""
    entries = load_and_verify()
    idx = len(entries) + 1
    timestamp = datetime.utcnow().isoformat() + "Z"
    prev_hash = "0" * 64 if not entries else entries[-1]["hash"]
    hash_val = compute_hash(prev_hash, content, timestamp, idx)

    new_entry = {
        "idx": idx,
        "timestamp": timestamp,
        "content": content,
        "prev_hash": prev_hash,
        "hash": hash_val
    }

    with open(FILE, "a") as f:
        f.write(json.dumps(new_entry) + "\n")

    print(f"Appended entry {idx}")

def replay():
    """Reconstruct and print state from external file only"""
    entries = load_and_verify()
    print("\nReplayed state:")
    reconstructed = [e["content"] for e in entries]
    print("Contents:", reconstructed)
    # Example simple state reconstruction (e.g., list of messages)
    print("Full entries:")
    for e in entries:
        print(f"{e['idx']}: {e['content']} (ts: {e['timestamp']})")

# Example run (uncomment to test)
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python persistence_prototype.py append <text> | replay")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "append" and len(sys.argv) >= 3:
        text = " ".join(sys.argv[2:])
        append(text)
    elif cmd == "replay":
        replay()
    else:
        print("Invalid command")
========================================================================


