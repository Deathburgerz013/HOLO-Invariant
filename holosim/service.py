"""Holo/Sim service runtime.

This module connects the major Holo/Sim subsystems into one runtime layer:
chain, operator, replay, artifact audit, rebirth, IDX config, and optional
SQLite slot persistence.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:
    from holosim.artifact_parser import ArtifactParser
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.core import HoloChain
    from holosim.idx_manager import get_idx_manager
    from holosim.operator import get_operator
    from holosim.rebirth_engine import run_rebirth
    from holosim.replay import ReplayEngine
    from holosim.slot_merkle_sqlite import SlotMerkleDB
    from holosim.typed_operational_authorization import (
        ACTION_SERVICE_APPEND,
        OperationalAuthorizationError,
        validate_operational_authorization,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.artifact_parser import ArtifactParser
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.core import HoloChain
    from holosim.idx_manager import get_idx_manager
    from holosim.operator import get_operator
    from holosim.rebirth_engine import run_rebirth
    from holosim.replay import ReplayEngine
    from holosim.slot_merkle_sqlite import SlotMerkleDB
    from holosim.typed_operational_authorization import (
        ACTION_SERVICE_APPEND,
        OperationalAuthorizationError,
        validate_operational_authorization,
    )


class HoloService:
    """Single runtime facade for Holo/Sim operations."""

    def __init__(
        self,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
        slot_db_path: str | Path | None = None,
    ) -> None:
        self.chain_path = Path(chain_path)
        self.chain = HoloChain(str(self.chain_path))
        self.operator = get_operator(self.chain_path)
        self.replay = ReplayEngine(self.chain_path)
        self.idx_manager = get_idx_manager(self.chain)
        self.artifact_parser = ArtifactParser()
        self.slot_db_path = slot_db_path

    def identity(self) -> Dict[str, Any]:
        """Return service identity metadata."""
        return {
            "service": "HoloService",
            "system": "Holo/Sim",
            "version": HOLOSIM_VERSION,
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "chain_file": str(self.chain_path),
        }

    def health(self) -> Dict[str, Any]:
        """Return chain health."""
        return self.chain.health()

    def verify(self) -> Dict[str, Any]:
        """Verify chain through ReplayEngine."""
        return self.replay.verify()

    def operator_summary(self) -> Dict[str, Any]:
        """Return high-level operator summary."""
        return self.operator.summary()

    def replay_latest(self) -> Optional[Dict[str, Any]]:
        """Return latest verified entry."""
        return self.replay.latest()

    def replay_timeline(self) -> list[Dict[str, Any]]:
        """Return compact replay timeline."""
        return self.replay.timeline()

    def search(self, query: str, limit: int = 20) -> list[Dict[str, Any]]:
        """Search verified chain entries."""
        return self.replay.search(query, limit=limit)

    def append(
        self,
        content: Any,
        *,
        compress: bool = True,
        mirror_to_slots: bool = False,
        tier: str = "standard",
        authorization: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Append only after explicit external acceptance is supplied."""
        canonical_content = json.dumps(
            content, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            default=str,
        )
        content_sha256 = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()
        try:
            if authorization is None:
                raise OperationalAuthorizationError("authorization is required")
            validate_operational_authorization(
                authorization,
                expected_action=ACTION_SERVICE_APPEND,
                expected_target_sha256=content_sha256,
            )
        except OperationalAuthorizationError as exc:
            return {
                "status": "BLOCKED",
                "commit_performed": False,
                "mutation": None,
                "entry": None,
                "slot": None,
                "authority": {
                    "accepted": False,
                    "source": "typed_external_authorization_required",
                    "authorization_hash": (
                        authorization.get("authorization_hash")
                        if isinstance(authorization, Mapping) else None
                    ),
                },
                "write_authority": "NONE",
                "reason": str(exc),
            }

        authority = {
            "accepted": True,
            "source": "external_human",
            "reviewer": authorization["actor_id"],
            "approval_reference": authorization["approval_reference"],
        }
        payload = {
            "type": "service_append",
            "source": "HoloService",
            "active_hash": ACTIVE_HASH,
            "content_sha256": content_sha256,
            "content": content,
            "authority": authority,
            "operational_authorization": dict(authorization),
        }

        entry = self.chain.append(payload, compress=compress)

        result: Dict[str, Any] = {
            "status": "COMMITTED",
            "commit_performed": True,
            "mutation": {"append": entry},
            "entry": entry,
            "slot": None,
            "authority": authority,
            "operational_authorization": dict(authorization),
            "write_authority": "EXTERNAL_HUMAN",
        }

        if mirror_to_slots:
            with self.open_slot_db() as db:
                slot = db.append_slot(
                    str(content),
                    tier=tier,
                    metadata={
                        "source": "HoloService",
                        "chain_idx": entry.get("idx"),
                        "chain_hash": entry.get("hash"),
                        "active_hash": ACTIVE_HASH,
                    },
                )
                result["slot"] = slot
                result["mutation"]["slot"] = slot

        return result

    def rebirth(self, event: str = "MANUAL_OVERRIDE") -> Dict[str, Any]:
        """Run configured rebirth event."""
        return run_rebirth(event)

    def idx_config(self) -> Dict[str, Any]:
        """Return current IDX config."""
        return self.idx_manager.get_core_config()

    def audit(self, path: str | Path | None = None) -> Dict[str, Any]:
        """Run artifact audit."""
        return self.artifact_parser.audit_caps(path)

    def open_slot_db(self) -> SlotMerkleDB:
        """Open optional SQLite slot backend."""
        if self.slot_db_path is None:
            return SlotMerkleDB()
        return SlotMerkleDB(self.slot_db_path)

    def slot_health(self) -> Dict[str, Any]:
        """Return SlotMerkleDB health."""
        with self.open_slot_db() as db:
            return db.health()

    def status(self) -> Dict[str, Any]:
        """Return compact service-wide status."""
        health = self.health()
        verify = self.verify()

        return {
            "identity": self.identity(),
            "health": {
                "recommendation": health.get("recommendation"),
                "total_entries": health.get("total_entries"),
                "chain_age_days": health.get("chain_age_days"),
                "compression_ratio": health.get("compression_ratio"),
            },
            "verify": verify,
            "idx": {
                "anchor": self.idx_config().get("anchor"),
                "active_hash": self.idx_config().get("active_hash"),
            },
        }


def get_service(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    slot_db_path: str | Path | None = None,
) -> HoloService:
    """Create a HoloService instance."""
    return HoloService(chain_path=chain_path, slot_db_path=slot_db_path)


if __name__ == "__main__":
    service = get_service()
    print(service.status())
