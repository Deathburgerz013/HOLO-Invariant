"""Deterministic continuity checkpoints built from a verified HoloChain."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from holosim.core import HoloChain


CHECKPOINT_VERSION = 1


def _canonical_hash(value: Any) -> str:
    """Return a deterministic SHA-256 hash for JSON-compatible data."""
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_continuity_checkpoint(chain: HoloChain) -> Dict[str, Any]:
    """
    Build a deterministic reconstruction checkpoint from a verified chain.

    The checkpoint preserves:
    - source-chain identity,
    - original claim order,
    - current effective content,
    - correction lineage,
    - current revalidation status.
    """
    entries = chain.load_and_verify()
    if not entries:
        raise ValueError("Cannot build a continuity checkpoint from an empty chain")

    claim_index = chain.get_claim_index()

    claims = []
    for claim in claim_index:
        item = {
            "idx": claim["idx"],
            "content": claim["content"],
            "content_hash": claim["content_hash"],
            "status": claim["status"],
            "correction_history": list(claim["correction_history"]),
            "revalidation_history": list(claim["revalidation_history"]),
        }

        if "corrected_by" in claim:
            item["corrected_by"] = claim["corrected_by"]

        if "revalidated_by" in claim:
            item["revalidated_by"] = claim["revalidated_by"]

        claims.append(item)

    checkpoint_body = {
        "version": CHECKPOINT_VERSION,
        "source": {
            "root_hash": entries[-1]["hash"],
            "total_entries": len(entries),
            "chain_version": chain.VERSION,
        },
        "claims": claims,
    }

    return {
        **checkpoint_body,
        "checkpoint_hash": _canonical_hash(checkpoint_body),
    }


def verify_continuity_checkpoint(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify a continuity checkpoint without access to the source chain.

    Verification checks:
    - top-level structure,
    - supported version,
    - ordered unique claim indices,
    - deterministic content hashes,
    - deterministic checkpoint hash.
    """
    if not isinstance(checkpoint, dict):
        raise TypeError("checkpoint must be a dictionary")

    required = {"version", "source", "claims", "checkpoint_hash"}
    missing = required.difference(checkpoint)
    if missing:
        raise ValueError(
            f"Checkpoint missing required fields: {sorted(missing)}"
        )

    if checkpoint["version"] != CHECKPOINT_VERSION:
        raise ValueError(
            f"Unsupported checkpoint version: {checkpoint['version']}"
        )

    source = checkpoint["source"]
    if not isinstance(source, dict):
        raise ValueError("Checkpoint source must be a dictionary")

    for field in ("root_hash", "total_entries", "chain_version"):
        if field not in source:
            raise ValueError(f"Checkpoint source missing field: {field}")

    if not isinstance(source["root_hash"], str) or len(source["root_hash"]) != 64:
        raise ValueError("Checkpoint source root_hash must be a 64-character string")

    if (
        not isinstance(source["total_entries"], int)
        or isinstance(source["total_entries"], bool)
        or source["total_entries"] < 1
    ):
        raise ValueError("Checkpoint source total_entries must be positive")

    claims = checkpoint["claims"]
    if not isinstance(claims, list):
        raise ValueError("Checkpoint claims must be a list")

    seen_indices = set()
    previous_idx = 0

    for position, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"Claim at position {position} must be a dictionary")

        for field in (
            "idx",
            "content",
            "content_hash",
            "status",
            "correction_history",
            "revalidation_history",
        ):
            if field not in claim:
                raise ValueError(
                    f"Claim at position {position} missing field: {field}"
                )

        idx = claim["idx"]
        if (
            not isinstance(idx, int)
            or isinstance(idx, bool)
            or idx < 1
        ):
            raise ValueError(f"Claim at position {position} has invalid idx")

        if idx in seen_indices:
            raise ValueError(f"Duplicate claim idx: {idx}")

        if idx <= previous_idx:
            raise ValueError("Claims must be ordered by increasing idx")

        expected_content_hash = _canonical_hash(claim["content"])
        if claim["content_hash"] != expected_content_hash:
            raise ValueError(f"Claim content hash mismatch at idx {idx}")

        if not isinstance(claim["correction_history"], list):
            raise ValueError(f"Claim correction_history must be a list at idx {idx}")

        if not isinstance(claim["revalidation_history"], list):
            raise ValueError(
                f"Claim revalidation_history must be a list at idx {idx}"
            )

        seen_indices.add(idx)
        previous_idx = idx

    checkpoint_body = {
        "version": checkpoint["version"],
        "source": checkpoint["source"],
        "claims": checkpoint["claims"],
    }
    expected_checkpoint_hash = _canonical_hash(checkpoint_body)

    if checkpoint["checkpoint_hash"] != expected_checkpoint_hash:
        raise ValueError("Checkpoint hash mismatch")

    return {
        "valid": True,
        "version": checkpoint["version"],
        "root_hash": source["root_hash"],
        "claim_count": len(claims),
        "checkpoint_hash": checkpoint["checkpoint_hash"],
    }
