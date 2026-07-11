from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import struct
import tempfile
import time
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    zstd = None
    ZSTD_AVAILABLE = False


FILE = "holo_merkle.jsonl"
USE_COMPRESSION = True
COMPRESSION_LEVEL = 3

FORMAT_VERSION = 2
ZERO_ROOT = "0" * 64

MAGIC_RAW = b"RAW0"
MAGIC_ZSTD = b"ZSTD"
MAGIC_ZLIB = b"ZLIB"
FRAME_MAGICS = {MAGIC_RAW, MAGIC_ZSTD, MAGIC_ZLIB}
FRAME_HEADER_SIZE = 8


class MerklePersistenceError(RuntimeError):
    """Base error for Merkle persistence failures."""


class MerkleFormatError(MerklePersistenceError):
    """Raised when the persistence file is malformed or truncated."""


class MerkleIntegrityError(MerklePersistenceError):
    """Raised when an entry, root, index, or proof fails verification."""


def sha256(data: bytes) -> str:
    """Return a lowercase SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for hashing."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _validate_hash(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise MerkleIntegrityError(f"{field_name} must be a 64-character SHA-256 hex string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise MerkleIntegrityError(f"{field_name} is not valid hexadecimal") from exc
    return value.lower()


def _merkle_root_from_hashes(leaves: Sequence[str]) -> str:
    """Build a Merkle root from already-hashed leaves."""
    if not leaves:
        return ZERO_ROOT

    level = [_validate_hash(leaf, "leaf hash") for leaf in leaves]

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        level = [
            sha256((level[index] + level[index + 1]).encode("ascii"))
            for index in range(0, len(level), 2)
        ]

    return level[0]


def _legacy_leaf_hash(entry: dict[str, Any]) -> str:
    """Hash an original-format entry exactly as it was stored."""
    return sha256(_canonical_json_bytes(entry))


def _entry_leaf_hash(entry: dict[str, Any]) -> str:
    """
    Return the stable leaf hash for an entry.

    Version 2 entries store an explicit entry_hash that excludes merkle_root,
    avoiding the self-reference present in the original format. Legacy entries
    remain readable and use their full stored JSON as the leaf material.
    """
    if entry.get("format_version") == FORMAT_VERSION:
        return _validate_hash(entry.get("entry_hash"), "entry_hash")
    return _legacy_leaf_hash(entry)


def build_merkle_root(entries: Sequence[dict[str, Any]]) -> str:
    """Build the current root for legacy and version 2 entries."""
    return _merkle_root_from_hashes([_entry_leaf_hash(entry) for entry in entries])


def _entry_payload(
    *,
    idx: int,
    timestamp: str,
    content: str,
    prev_merkle_root: str,
) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "idx": idx,
        "timestamp": timestamp,
        "content": content,
        "prev_merkle_root": prev_merkle_root,
    }


def generate_merkle_proof(
    entries: Sequence[dict[str, Any]],
    index: int,
) -> list[dict[str, str]]:
    """
    Generate a proof for a zero-based entry index.

    Each proof step records both the sibling hash and whether that sibling is
    on the left or right, so verification does not depend on an external index.
    """
    if index < 0 or index >= len(entries):
        raise IndexError("Merkle proof index is out of range")

    level = [_entry_leaf_hash(entry) for entry in entries]
    current_index = index
    proof: list[dict[str, str]] = []

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        sibling_index = current_index ^ 1
        proof.append(
            {
                "hash": level[sibling_index],
                "position": "left" if sibling_index < current_index else "right",
            }
        )

        current_index //= 2
        level = [
            sha256((level[position] + level[position + 1]).encode("ascii"))
            for position in range(0, len(level), 2)
        ]

    return proof


def verify_merkle_proof(
    leaf_hash: str,
    proof: Sequence[dict[str, str]],
    root: str,
    index: int | None = None,
) -> bool:
    """
    Verify a direction-aware Merkle proof.

    The optional index argument is accepted for compatibility with the older
    function signature but is no longer required.
    """
    del index

    try:
        current = _validate_hash(leaf_hash, "leaf_hash")
        expected_root = _validate_hash(root, "root")

        for step in proof:
            sibling = _validate_hash(step.get("hash"), "proof sibling")
            position = step.get("position")

            if position == "left":
                current = sha256((sibling + current).encode("ascii"))
            elif position == "right":
                current = sha256((current + sibling).encode("ascii"))
            else:
                return False

        return current == expected_root
    except MerkleIntegrityError:
        return False


def _encode_frame(data: bytes, use_compression: bool, compression_level: int) -> bytes:
    """Encode one JSON record as a length-prefixed frame."""
    if not use_compression:
        payload = data
        magic = MAGIC_RAW
    elif ZSTD_AVAILABLE:
        compressor = zstd.ZstdCompressor(level=compression_level)
        payload = compressor.compress(data)
        magic = MAGIC_ZSTD
    else:
        level = max(0, min(compression_level, 9))
        payload = zlib.compress(data, level=level)
        magic = MAGIC_ZLIB

    return magic + struct.pack(">I", len(payload)) + payload


def _decode_frame(magic: bytes, payload: bytes) -> bytes:
    try:
        if magic == MAGIC_RAW:
            return payload

        if magic == MAGIC_ZSTD:
            if not ZSTD_AVAILABLE:
                raise MerkleFormatError(
                    "This file contains ZSTD frames, but the zstandard package is not installed"
                )
            return zstd.ZstdDecompressor().decompress(payload)

        if magic == MAGIC_ZLIB:
            return zlib.decompress(payload)
    except MerkleFormatError:
        raise
    except Exception as exc:
        raise MerkleFormatError("Compressed frame could not be decompressed") from exc

    raise MerkleFormatError(f"Unknown frame magic: {magic!r}")


@contextmanager
def _exclusive_lock(file_path: Path, timeout: float = 10.0) -> Iterator[None]:
    """
    Hold an exclusive cross-platform lock for a complete store operation.

    The lock file lives in the system temporary directory, so repository state
    is not polluted by lock artifacts.
    """
    absolute = str(file_path.resolve()).encode("utf-8")
    lock_name = f"holosim-merkle-{sha256(absolute)[:20]}.lock"
    lock_path = Path(tempfile.gettempdir()) / lock_name
    deadline = time.monotonic() + timeout

    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()

        acquired = False

        while not acquired:
            try:
                lock_file.seek(0)

                if platform.system() == "Windows":
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(
                        lock_file.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )

                acquired = True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for Merkle store lock: {file_path}")
                time.sleep(0.05)

        try:
            yield
        finally:
            lock_file.seek(0)

            if platform.system() == "Windows":
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class MerkleStore:
    """Strict, append-only Merkle persistence store."""

    def __init__(
        self,
        file_path: str | Path = FILE,
        *,
        use_compression: bool = USE_COMPRESSION,
        compression_level: int = COMPRESSION_LEVEL,
        lock_timeout: float = 10.0,
    ) -> None:
        self.file_path = Path(file_path)
        self.use_compression = use_compression
        self.compression_level = compression_level
        self.lock_timeout = lock_timeout
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_records_unlocked(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []

        raw = self.file_path.read_bytes()
        entries: list[dict[str, Any]] = []
        position = 0
        record_number = 0

        while position < len(raw):
            record_number += 1

            if position + 4 <= len(raw) and raw[position:position + 4] in FRAME_MAGICS:
                if position + FRAME_HEADER_SIZE > len(raw):
                    raise MerkleFormatError(
                        f"Truncated frame header at byte {position}"
                    )

                magic = raw[position:position + 4]
                payload_length = struct.unpack(
                    ">I",
                    raw[position + 4:position + FRAME_HEADER_SIZE],
                )[0]
                payload_start = position + FRAME_HEADER_SIZE
                payload_end = payload_start + payload_length

                if payload_end > len(raw):
                    raise MerkleFormatError(
                        f"Truncated frame {record_number}: expected {payload_length} payload bytes"
                    )

                payload = raw[payload_start:payload_end]
                position = payload_end
                decoded = _decode_frame(magic, payload)
            else:
                # Strict legacy JSONL compatibility.
                newline = raw.find(b"\n", position)
                if newline == -1:
                    newline = len(raw)
                    next_position = len(raw)
                else:
                    next_position = newline + 1

                decoded = raw[position:newline]
                position = next_position

            if not decoded.strip():
                continue

            try:
                entry = json.loads(decoded.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise MerkleFormatError(
                    f"Invalid JSON in record {record_number}"
                ) from exc

            if not isinstance(entry, dict):
                raise MerkleFormatError(
                    f"Record {record_number} must contain a JSON object"
                )

            entries.append(entry)

        return entries

    def _validate_entries(self, entries: Sequence[dict[str, Any]]) -> str:
        validated: list[dict[str, Any]] = []

        for expected_idx, entry in enumerate(entries, start=1):
            idx = entry.get("idx")
            if idx != expected_idx:
                raise MerkleIntegrityError(
                    f"Index mismatch at entry {expected_idx}: found {idx!r}"
                )

            timestamp = entry.get("timestamp")
            content = entry.get("content")
            prev_root = _validate_hash(
                entry.get("prev_merkle_root"),
                f"prev_merkle_root at entry {expected_idx}",
            )

            if not isinstance(timestamp, str) or not timestamp:
                raise MerkleIntegrityError(
                    f"timestamp at entry {expected_idx} must be a non-empty string"
                )
            if not isinstance(content, str):
                raise MerkleIntegrityError(
                    f"content at entry {expected_idx} must be a string"
                )

            current_root = build_merkle_root(validated)
            if prev_root != current_root:
                raise MerkleIntegrityError(
                    f"Previous root mismatch at entry {expected_idx}"
                )

            if entry.get("format_version") == FORMAT_VERSION:
                payload = _entry_payload(
                    idx=idx,
                    timestamp=timestamp,
                    content=content,
                    prev_merkle_root=prev_root,
                )
                expected_entry_hash = sha256(_canonical_json_bytes(payload))
                stored_entry_hash = _validate_hash(
                    entry.get("entry_hash"),
                    f"entry_hash at entry {expected_idx}",
                )

                if stored_entry_hash != expected_entry_hash:
                    raise MerkleIntegrityError(
                        f"Entry hash mismatch at entry {expected_idx}"
                    )

                candidate = dict(entry)
                expected_root = _merkle_root_from_hashes(
                    [_entry_leaf_hash(item) for item in validated]
                    + [stored_entry_hash]
                )
                stored_root = _validate_hash(
                    candidate.get("merkle_root"),
                    f"merkle_root at entry {expected_idx}",
                )

                if stored_root != expected_root:
                    raise MerkleIntegrityError(
                        f"Merkle root mismatch at entry {expected_idx}"
                    )
            else:
                # Verify the original self-referential format exactly as it was created:
                # the current entry was hashed with merkle_root set to None.
                legacy_candidate = dict(entry)
                stored_root = _validate_hash(
                    legacy_candidate.get("merkle_root"),
                    f"legacy merkle_root at entry {expected_idx}",
                )
                legacy_candidate["merkle_root"] = None
                expected_root = _merkle_root_from_hashes(
                    [_legacy_leaf_hash(item) for item in validated]
                    + [_legacy_leaf_hash(legacy_candidate)]
                )

                if stored_root != expected_root:
                    raise MerkleIntegrityError(
                        f"Legacy Merkle root mismatch at entry {expected_idx}"
                    )

            validated.append(dict(entry))

        return build_merkle_root(validated)

    def load(self) -> list[dict[str, Any]]:
        """Load and strictly verify every stored entry."""
        with _exclusive_lock(self.file_path, self.lock_timeout):
            entries = self._read_records_unlocked()
            self._validate_entries(entries)
            return entries

    def verify(self) -> dict[str, Any]:
        """Return verified store metadata."""
        with _exclusive_lock(self.file_path, self.lock_timeout):
            entries = self._read_records_unlocked()
            root = self._validate_entries(entries)

        return {
            "valid": True,
            "entries": len(entries),
            "merkle_root": root,
            "file": str(self.file_path),
            "format_version": FORMAT_VERSION,
        }

    def append(self, content: str) -> dict[str, Any]:
        """
        Atomically verify the store and append one new version 2 entry.

        The exclusive lock covers read, verification, root calculation, write,
        flush, and fsync, preventing competing writers from sharing an index.
        """
        if not isinstance(content, str):
            raise TypeError("content must be a string")

        with _exclusive_lock(self.file_path, self.lock_timeout):
            entries = self._read_records_unlocked()
            prev_root = self._validate_entries(entries)

            idx = len(entries) + 1
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            payload = _entry_payload(
                idx=idx,
                timestamp=timestamp,
                content=content,
                prev_merkle_root=prev_root,
            )
            entry_hash = sha256(_canonical_json_bytes(payload))
            new_root = _merkle_root_from_hashes(
                [_entry_leaf_hash(entry) for entry in entries] + [entry_hash]
            )

            new_entry = {
                **payload,
                "entry_hash": entry_hash,
                "merkle_root": new_root,
            }

            record = _canonical_json_bytes(new_entry) + b"\n"
            frame = _encode_frame(
                record,
                self.use_compression,
                self.compression_level,
            )

            with self.file_path.open("ab") as store_file:
                store_file.write(frame)
                store_file.flush()
                os.fsync(store_file.fileno())

        return new_entry

    def replay(self) -> dict[str, Any]:
        """Load the verified store and return replay data."""
        entries = self.load()
        return {
            "entries": entries,
            "merkle_root": build_merkle_root(entries),
            "count": len(entries),
        }


def load_merkle_entries(file_path: str | Path = FILE) -> list[dict[str, Any]]:
    """Compatibility wrapper for the original module API."""
    entries = MerkleStore(file_path).load()
    print(f"✅ Loaded and verified {len(entries)} Merkle entries.")
    return entries


def append_merkle(content: str, file_path: str | Path = FILE) -> dict[str, Any]:
    """Compatibility wrapper for appending one entry."""
    entry = MerkleStore(file_path).append(content)
    print(
        f"✅ Appended entry {entry['idx']} | "
        f"Merkle Root: {entry['merkle_root'][:16]}..."
    )
    return entry


def replay_merkle(file_path: str | Path = FILE) -> dict[str, Any]:
    """Replay the verified store and demonstrate a proof for the final entry."""
    store = MerkleStore(file_path)
    replay = store.replay()
    entries = replay["entries"]
    root = replay["merkle_root"]

    print("\n=== Replayed HOLO Merkle State ===")
    print(f"Current Merkle Root: {root}")

    for entry in entries:
        preview = entry["content"][:120]
        suffix = "..." if len(entry["content"]) > 120 else ""
        print(f"{entry['idx']:3d} | {entry['timestamp']} | {preview}{suffix}")

    if entries:
        last_index = len(entries) - 1
        proof = generate_merkle_proof(entries, last_index)
        leaf = _entry_leaf_hash(entries[last_index])
        valid = verify_merkle_proof(leaf, proof, root)
        print(f"✅ Merkle proof for entry {entries[last_index]['idx']} verified: {valid}")

    return replay


def _run_self_test() -> None:
    """Run a destructive test only against a temporary file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "self_test.holo"
        store = MerkleStore(path)

        first = store.append("alpha")
        second = store.append("beta")
        third = store.append("gamma")

        verified = store.verify()
        assert verified["valid"] is True
        assert verified["entries"] == 3
        assert [first["idx"], second["idx"], third["idx"]] == [1, 2, 3]

        entries = store.load()
        proof = generate_merkle_proof(entries, 1)
        assert verify_merkle_proof(
            _entry_leaf_hash(entries[1]),
            proof,
            verified["merkle_root"],
        )

        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        path.write_bytes(raw)

        try:
            store.verify()
        except MerklePersistenceError:
            pass
        else:
            raise AssertionError("Tampering was not detected")

    print("✅ Merkle persistence self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strict append-only Merkle persistence for Holo/Sim."
    )
    parser.add_argument(
        "--file",
        "-f",
        default=FILE,
        help="Persistence file path",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    append_parser = subparsers.add_parser("append", help="Append one text entry")
    append_parser.add_argument("text", nargs="+", help="Text to append")

    subparsers.add_parser("replay", help="Replay and verify the store")
    subparsers.add_parser("verify", help="Verify the store")
    subparsers.add_parser("self-test", help="Run an isolated temporary self-test")

    args = parser.parse_args()

    if args.command == "append":
        append_merkle(" ".join(args.text), args.file)
    elif args.command == "replay":
        replay_merkle(args.file)
    elif args.command == "verify":
        print(json.dumps(MerkleStore(args.file).verify(), indent=2))
    elif args.command == "self-test":
        _run_self_test()
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
