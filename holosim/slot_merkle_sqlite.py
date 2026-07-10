"""SQLite-backed slot and Merkle persistence for Holo/Sim.

Provides:

- append-only indexed slots
- deterministic SHA-256 content hashes
- duplicate-content detection
- Merkle root recorded for every committed prefix
- previous-root linkage between slots
- full replay and integrity verification
- Merkle inclusion proof generation and verification
- explicit CLI operations

The current implementation rebuilds the Merkle root from all content hashes
when appending. SQLite insertion is constant-time in practical terms, but the
Merkle calculation is O(n). A Merkle Mountain Range may replace this later.

This backend is separate from the canonical HoloChain JSONL store. It should
not silently replace or mutate that store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

DEFAULT_DB_FILE = "holo_slots.db"
BACKEND_TYPE = "holo_slot_merkle_sqlite"
BACKEND_VERSION = "0.2"

VALID_TIERS = {
    "critical",
    "standard",
    "archive",
}

ZERO_HASH = "0" * 64


def utc_now() -> str:
    """Return a timezone-aware ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def sha256(data: str | bytes) -> str:
    """Return a SHA-256 hexadecimal digest."""
    if isinstance(data, str):
        data = data.encode("utf-8")

    return hashlib.sha256(data).hexdigest()


def build_merkle_root(leaves: Sequence[str]) -> str:
    """Build a deterministic binary Merkle root from hexadecimal leaf hashes."""
    if not leaves:
        return ZERO_HASH

    level = list(leaves)

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        level = [
            sha256(level[index] + level[index + 1])
            for index in range(0, len(level), 2)
        ]

    return level[0]


def generate_merkle_proof(
    leaves: Sequence[str],
    index: int,
) -> List[Dict[str, str]]:
    """Generate an inclusion proof for one leaf.

    Each proof item records the sibling hash and whether it belongs on the
    left or right side during reconstruction.
    """
    if index < 0 or index >= len(leaves):
        raise IndexError("Merkle proof index is outside the leaf range.")

    proof: List[Dict[str, str]] = []
    level = list(leaves)
    current_index = index

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        if current_index % 2 == 0:
            sibling_index = current_index + 1
            position = "right"
        else:
            sibling_index = current_index - 1
            position = "left"

        proof.append(
            {
                "position": position,
                "hash": level[sibling_index],
            }
        )

        next_level = [
            sha256(level[offset] + level[offset + 1])
            for offset in range(0, len(level), 2)
        ]

        current_index //= 2
        level = next_level

    return proof


def verify_merkle_proof(
    leaf_hash: str,
    proof: Iterable[Mapping[str, str]],
    expected_root: str,
) -> bool:
    """Verify one Merkle inclusion proof."""
    current = leaf_hash

    for step in proof:
        sibling = step.get("hash")
        position = step.get("position")

        if not sibling or position not in {"left", "right"}:
            return False

        if position == "left":
            current = sha256(sibling + current)
        else:
            current = sha256(current + sibling)

    return current == expected_root


class SlotMerkleDB:
    """Append-only SQLite slot store with Merkle prefix roots."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_FILE,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        self._configure_connection()
        self._init_db()

    def _configure_connection(self) -> None:
        """Configure SQLite for safe local persistence."""
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = FULL")

    def _init_db(self) -> None:
        """Create the schema without modifying existing slot data."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS slots (
                idx INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                prev_root TEXT NOT NULL,
                merkle_root TEXT NOT NULL,
                tier TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                content TEXT
            )
            """
        )

        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_slots_timestamp
            ON slots(timestamp)
            """
        )

        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_slots_tier
            ON slots(tier)
            """
        )

        self.conn.commit()

    def identity(self) -> Dict[str, Any]:
        """Return backend identity without changing persistence."""
        return {
            "type": BACKEND_TYPE,
            "version": BACKEND_VERSION,
            "database": str(self.db_path),
            "entries": self.count(),
            "current_root": self.get_current_root(),
        }

    def count(self) -> int:
        """Return the number of committed slots."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM slots"
        ).fetchone()

        return int(row["total"]) if row else 0

    def get_current_root(self) -> str:
        """Return the newest committed Merkle root."""
        row = self.conn.execute(
            """
            SELECT merkle_root
            FROM slots
            ORDER BY idx DESC
            LIMIT 1
            """
        ).fetchone()

        return str(row["merkle_root"]) if row else ZERO_HASH

    def get_content_hashes(self) -> List[str]:
        """Return committed content hashes in slot order."""
        rows = self.conn.execute(
            """
            SELECT content_hash
            FROM slots
            ORDER BY idx
            """
        ).fetchall()

        return [str(row["content_hash"]) for row in rows]

    def _get_next_idx(self) -> int:
        """Return the next append-only slot index."""
        row = self.conn.execute(
            "SELECT MAX(idx) AS maximum_idx FROM slots"
        ).fetchone()

        maximum = row["maximum_idx"] if row else None
        return int(maximum or 0) + 1

    def append_slot(
        self,
        content: str,
        *,
        tier: str = "standard",
        metadata: Optional[Mapping[str, Any]] = None,
        retain_content: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Append one unique slot and return its commit record.

        Raw content is retained automatically for critical-tier slots.
        For other tiers, pass retain_content=True when raw persistence is
        explicitly required.
        """
        if not isinstance(content, str):
            raise TypeError("content must be a string.")

        if not content.strip():
            raise ValueError("content cannot be empty.")

        normalized_tier = tier.strip().lower()

        if normalized_tier not in VALID_TIERS:
            allowed = ", ".join(sorted(VALID_TIERS))
            raise ValueError(f"tier must be one of: {allowed}")

        metadata_dict = dict(metadata or {})
        metadata_json = canonical_json(metadata_dict)
        content_hash = sha256(content)

        existing = self.conn.execute(
            """
            SELECT idx, merkle_root
            FROM slots
            WHERE content_hash = ?
            """,
            (content_hash,),
        ).fetchone()

        if existing:
            return {
                "status": "already_fused",
                "idx": int(existing["idx"]),
                "content_hash": content_hash,
                "merkle_root": str(existing["merkle_root"]),
            }

        previous_root = self.get_current_root()
        content_hashes = self.get_content_hashes()
        content_hashes.append(content_hash)

        new_root = build_merkle_root(content_hashes)
        idx = self._get_next_idx()
        timestamp = utc_now()

        should_retain = (
            normalized_tier == "critical"
            if retain_content is None
            else bool(retain_content)
        )

        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO slots (
                        idx,
                        timestamp,
                        content_hash,
                        prev_root,
                        merkle_root,
                        tier,
                        metadata_json,
                        content
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idx,
                        timestamp,
                        content_hash,
                        previous_root,
                        new_root,
                        normalized_tier,
                        metadata_json,
                        content if should_retain else None,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(
                "Slot append failed due to an integrity constraint."
            ) from exc

        return {
            "status": "fused",
            "idx": idx,
            "timestamp": timestamp,
            "tier": normalized_tier,
            "content_hash": content_hash,
            "prev_root": previous_root,
            "merkle_root": new_root,
            "content_retained": should_retain,
        }

    def get_slot(self, idx: int) -> Optional[Dict[str, Any]]:
        """Read one slot by its append index."""
        row = self.conn.execute(
            """
            SELECT
                idx,
                timestamp,
                content_hash,
                prev_root,
                merkle_root,
                tier,
                metadata_json,
                content
            FROM slots
            WHERE idx = ?
            """,
            (idx,),
        ).fetchone()

        return self._row_to_dict(row) if row else None

    def replay(
        self,
        *,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return slots in chronological order.

        When limit is supplied, the newest N slots are returned while their
        final output ordering remains oldest-to-newest.
        """
        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than zero.")

        if limit is None:
            rows = self.conn.execute(
                """
                SELECT
                    idx,
                    timestamp,
                    content_hash,
                    prev_root,
                    merkle_root,
                    tier,
                    metadata_json,
                    content
                FROM slots
                ORDER BY idx
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM (
                    SELECT
                        idx,
                        timestamp,
                        content_hash,
                        prev_root,
                        merkle_root,
                        tier,
                        metadata_json,
                        content
                    FROM slots
                    ORDER BY idx DESC
                    LIMIT ?
                )
                ORDER BY idx
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def create_proof(self, idx: int) -> Dict[str, Any]:
        """Create a Merkle inclusion proof for one committed slot."""
        slot = self.get_slot(idx)

        if slot is None:
            raise KeyError(f"Slot {idx} does not exist.")

        hashes = self.get_content_hashes()
        leaf_index = idx - 1

        if leaf_index < 0 or leaf_index >= len(hashes):
            raise RuntimeError("Slot indexes are not contiguous.")

        proof = generate_merkle_proof(hashes, leaf_index)
        root = build_merkle_root(hashes)

        return {
            "status": "ok",
            "idx": idx,
            "leaf_index": leaf_index,
            "content_hash": slot["content_hash"],
            "proof": proof,
            "root": root,
            "verified": verify_merkle_proof(
                slot["content_hash"],
                proof,
                root,
            ),
        }

    def verify_chain(self) -> Dict[str, Any]:
        """Verify slot order, previous-root links, and every prefix root."""
        rows = self.conn.execute(
            """
            SELECT
                idx,
                content_hash,
                prev_root,
                merkle_root
            FROM slots
            ORDER BY idx
            """
        ).fetchall()

        violations: List[Dict[str, Any]] = []
        prefix_hashes: List[str] = []
        expected_previous_root = ZERO_HASH

        for expected_idx, row in enumerate(rows, start=1):
            actual_idx = int(row["idx"])
            content_hash = str(row["content_hash"])
            stored_previous_root = str(row["prev_root"])
            stored_root = str(row["merkle_root"])

            if actual_idx != expected_idx:
                violations.append(
                    {
                        "idx": actual_idx,
                        "type": "index_gap",
                        "expected": expected_idx,
                        "actual": actual_idx,
                    }
                )

            if stored_previous_root != expected_previous_root:
                violations.append(
                    {
                        "idx": actual_idx,
                        "type": "previous_root_mismatch",
                        "expected": expected_previous_root,
                        "actual": stored_previous_root,
                    }
                )

            prefix_hashes.append(content_hash)
            expected_root = build_merkle_root(prefix_hashes)

            if stored_root != expected_root:
                violations.append(
                    {
                        "idx": actual_idx,
                        "type": "merkle_root_mismatch",
                        "expected": expected_root,
                        "actual": stored_root,
                    }
                )

            expected_previous_root = expected_root

        valid = not violations

        return {
            "status": "PASS" if valid else "FAIL",
            "valid": valid,
            "entries": len(rows),
            "current_root": (
                expected_previous_root if rows else ZERO_HASH
            ),
            "violations": violations,
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row into a safe public dictionary."""
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, json.JSONDecodeError):
            metadata = {
                "_decode_error": True,
                "_raw": row["metadata_json"],
            }

        return {
            "idx": int(row["idx"]),
            "timestamp": str(row["timestamp"]),
            "content_hash": str(row["content_hash"]),
            "prev_root": str(row["prev_root"]),
            "merkle_root": str(row["merkle_root"]),
            "tier": str(row["tier"]),
            "metadata": metadata,
            "content": row["content"],
        }

    def close(self) -> None:
        """Close the SQLite connection."""
        self.conn.close()

    def __enter__(self) -> "SlotMerkleDB":
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()


def get_slot_db(
    db_path: str | Path = DEFAULT_DB_FILE,
) -> SlotMerkleDB:
    """Create a slot database instance."""
    return SlotMerkleDB(db_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Operate the Holo/Sim SQLite Merkle slot backend."
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_FILE,
        help="SQLite database path",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "identity",
        help="Show backend identity",
    )

    append_parser = subparsers.add_parser(
        "append",
        help="Append one slot",
    )
    append_parser.add_argument("content")
    append_parser.add_argument(
        "--tier",
        choices=sorted(VALID_TIERS),
        default="standard",
    )
    append_parser.add_argument(
        "--metadata",
        default="{}",
        help="Metadata JSON object",
    )
    append_parser.add_argument(
        "--retain-content",
        action="store_true",
    )

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay committed slots",
    )
    replay_parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    proof_parser = subparsers.add_parser(
        "proof",
        help="Create and verify a slot proof",
    )
    proof_parser.add_argument(
        "idx",
        type=int,
    )

    subparsers.add_parser(
        "verify",
        help="Verify every slot and root",
    )

    args = parser.parse_args()

    try:
        metadata = (
            json.loads(args.metadata)
            if args.command == "append"
            else {}
        )
    except json.JSONDecodeError as exc:
        raise SystemExit("--metadata must contain valid JSON.") from exc

    if not isinstance(metadata, dict):
        raise SystemExit("--metadata must decode to a JSON object.")

    with get_slot_db(args.db) as database:
        if args.command == "identity":
            result = database.identity()

        elif args.command == "append":
            result = database.append_slot(
                args.content,
                tier=args.tier,
                metadata=metadata,
                retain_content=(
                    True if args.retain_content else None
                ),
            )

        elif args.command == "replay":
            result = {
                "status": "ok",
                "entries": database.replay(limit=args.limit),
            }

        elif args.command == "proof":
            result = database.create_proof(args.idx)

        elif args.command == "verify":
            result = database.verify_chain()

        else:
            raise SystemExit(f"Unknown command: {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.command == "verify":
        raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()