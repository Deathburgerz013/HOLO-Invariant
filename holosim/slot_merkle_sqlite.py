from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from holosim.config import ACTIVE_HASH, ANCHOR, REPO_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import ACTIVE_HASH, ANCHOR, REPO_ROOT


DEFAULT_DB_FILE = REPO_ROOT / "holo_slots.db"
ZERO_HASH = "0" * 64
CRITICAL_TIER = "critical"


def sha256(data: str | bytes) -> str:
    """Return SHA-256 hex digest for text or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class SlotMerkleDB:
    """SQLite-backed append-only slot store with Merkle verification."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_FILE) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS slots (
                idx INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                prev_hash TEXT NOT NULL,
                merkle_root TEXT NOT NULL,
                tier TEXT DEFAULT 'standard',
                metadata TEXT,
                content TEXT
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON slots(content_hash)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON slots(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tier ON slots(tier)")
        self.conn.commit()

    def close(self) -> None:
        """Close the SQLite connection."""
        self.conn.close()

    def __enter__(self) -> "SlotMerkleDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_next_idx(self) -> int:
        row = self.conn.execute("SELECT MAX(idx) AS max_idx FROM slots").fetchone()
        return int(row["max_idx"] or 0) + 1

    def get_current_root(self) -> str:
        """Return latest Merkle root or zero hash for empty DB."""
        row = self.conn.execute(
            "SELECT merkle_root FROM slots ORDER BY idx DESC LIMIT 1"
        ).fetchone()
        return str(row["merkle_root"]) if row else ZERO_HASH

    def _build_merkle_root(self, leaves: List[str]) -> str:
        """Build Merkle root from ordered content hashes."""
        if not leaves:
            return ZERO_HASH

        layer = leaves[:]
        while len(layer) > 1:
            if len(layer) % 2 == 1:
                layer.append(layer[-1])
            layer = [sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]

        return layer[0]

    def _all_content_hashes(self) -> List[str]:
        rows = self.conn.execute("SELECT content_hash FROM slots ORDER BY idx").fetchall()
        return [str(row["content_hash"]) for row in rows]

    def append_slot(
        self,
        content: str,
        tier: str = "standard",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append a new slot unless identical content is already fused."""
        metadata = dict(metadata or {})
        metadata.setdefault("active_hash", ACTIVE_HASH)
        metadata.setdefault("anchor", ANCHOR)

        content_hash = sha256(content)

        existing = self.conn.execute(
            "SELECT idx, merkle_root FROM slots WHERE content_hash = ?",
            (content_hash,),
        ).fetchone()

        if existing:
            print(f"⚡ Already fused (same-hash skip): {content_hash[:16]}...")
            return {
                "status": "already_fused",
                "idx": int(existing["idx"]),
                "content_hash": content_hash,
                "merkle_root": str(existing["merkle_root"]),
            }

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prev_hash = self.get_current_root()
        idx = self._get_next_idx()

        all_hashes = self._all_content_hashes()
        all_hashes.append(content_hash)
        new_root = self._build_merkle_root(all_hashes)

        meta_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        stored_content = content if tier == CRITICAL_TIER else None

        self.conn.execute(
            """
            INSERT INTO slots (
                idx,
                timestamp,
                content_hash,
                prev_hash,
                merkle_root,
                tier,
                metadata,
                content
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idx,
                timestamp,
                content_hash,
                prev_hash,
                new_root,
                tier,
                meta_json,
                stored_content,
            ),
        )
        self.conn.commit()

        print(
            f"✅ Fused slot {idx} | Tier: {tier} | "
            f"Root: {new_root[:16]}... | Hash: {content_hash[:16]}..."
        )

        return {
            "status": "fused",
            "idx": idx,
            "timestamp": timestamp,
            "merkle_root": new_root,
            "content_hash": content_hash,
            "tier": tier,
        }

    def replay(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Replay slots in order, optionally limited to the latest N results."""
        rows = self.conn.execute(
            """
            SELECT idx, timestamp, content_hash, merkle_root, tier, metadata
            FROM slots
            ORDER BY idx
            """
        ).fetchall()

        selected = rows[-limit:] if limit else rows
        root = self.get_current_root()

        print(f"\n=== Slot Merkle Replay | Current Root: {root[:16]}... ===")

        results: List[Dict[str, Any]] = []
        for row in selected:
            print(
                f"{int(row['idx']):4d} | {row['timestamp']} | "
                f"{str(row['tier']).upper():8} | {str(row['content_hash'])[:16]}..."
            )
            results.append(
                {
                    "idx": int(row["idx"]),
                    "timestamp": str(row["timestamp"]),
                    "content_hash": str(row["content_hash"]),
                    "merkle_root": str(row["merkle_root"]),
                    "tier": str(row["tier"]),
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                }
            )

        return results

    def verify_chain(self) -> bool:
        """Verify Merkle root consistency against ordered content hashes."""
        rows = self.conn.execute(
            "SELECT content_hash, merkle_root FROM slots ORDER BY idx"
        ).fetchall()

        if not rows:
            print("✅ Chain verification: PASS (empty)")
            return True

        computed = self._build_merkle_root([str(row["content_hash"]) for row in rows])
        latest_root = str(rows[-1]["merkle_root"])
        valid = computed == latest_root

        print(f"✅ Chain verification: {'PASS' if valid else 'FAIL'}")
        return valid

    def health(self) -> Dict[str, Any]:
        """Return compact backend health."""
        row = self.conn.execute("SELECT COUNT(*) AS count FROM slots").fetchone()
        total = int(row["count"] or 0)
        root = self.get_current_root()
        verified = self.verify_chain()

        return {
            "db_path": str(self.db_path),
            "total_slots": total,
            "merkle_root": root,
            "verified": verified,
            "active_hash": ACTIVE_HASH,
            "anchor": ANCHOR,
            "recommendation": "Healthy" if verified else "Merkle verification failed",
        }


if __name__ == "__main__":
    with SlotMerkleDB() as db:
        db.append_slot(
            "Human anchor: Canyon Brock Haney — HSSCE continuity verified",
            tier="critical",
        )
        db.append_slot(
            "Collection orchestrator delta fused via 10_Collection_Orchestrator",
            tier="standard",
        )
        db.replay(limit=5)
        db.verify_chain()