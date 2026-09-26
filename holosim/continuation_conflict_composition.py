"""Compose continuity currentness with explicit competing-head detection.

Continuation is admissible only when an intact continuity-head binding check is CURRENT and an intact competing-head detection receipt reports NO_FORK. The composition does not infer currentness from absence of conflict, choose among competing heads, determine truth, mutate canonical state, or grant authority.
"""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash

HEAD_CHECK_TYPE = "continuity_head_binding_check"
FORK_CHECK_TYPE = "competing_head_detection_receipt"
RECEIPT_TYPE = "continuation_admissibility_receipt"
RECEIPT_VERSION = 1


class ContinuationConflictCompositionError(ValueError):
    """Raised when a supplied composition input is malformed or invalid."""


def _validate_hashed_receipt(
    receipt: Mapping[str, Any],
    *,
    expected_type: str,
    hash_field: str,
    label: str,
) -> str:
    if not isinstance(receipt, Mapping) or receipt.get("type") != expected_type:
        raise ContinuationConflictCompositionError(
            f"{label} must be a {expected_type}"
        )

    stored_hash = receipt.get(hash_field)
    if not isinstance(stored_hash, str) or not stored_hash:
        raise ContinuationConflictCompositionError(
            f"{label} requires {hash_field}"
        )

    body = {
        key: deepcopy(value)
        for key, value in receipt.items()
        if key != hash_field
    }
    try:
        if stable_hash(body) != stored_hash:
            raise ContinuationConflictCompositionError(
                f"{label} hash does not match content"
            )
    except CanonicalValueError as exc:
        raise ContinuationConflictCompositionError(str(exc)) from exc

    return stored_hash


def evaluate_continuation_admissibility(
    *,
    head_check: Mapping[str, Any],
    fork_check: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose independent currentness and fork checks fail closed."""

    head_check_hash = _validate_hashed_receipt(
        head_check,
        expected_type=HEAD_CHECK_TYPE,
        hash_field="check_hash",
        label="head_check",
    )
    fork_check_hash = _validate_hashed_receipt(
        fork_check,
        expected_type=FORK_CHECK_TYPE,
        hash_field="receipt_hash",
        label="fork_check",
    )

    head_status = head_check.get("status")
    fork_status = fork_check.get("status")

    if head_status not in {"CURRENT", "STALE", "INVALID", "UNKNOWN"}:
        raise ContinuationConflictCompositionError(
            "head_check has unsupported status"
        )
    if fork_status not in {"NO_FORK", "CONFLICT"}:
        raise ContinuationConflictCompositionError(
            "fork_check has unsupported status"
        )

    reasons: list[str] = []
    if head_status != "CURRENT":
        reasons.append(f"continuity_head_status_{head_status.lower()}")
    if fork_status == "CONFLICT":
        reasons.append("competing_heads_conflict")

    decision = "ALLOW" if not reasons else "BLOCK"

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "head_check_hash": head_check_hash,
        "fork_check_hash": fork_check_hash,
        "head_status": head_status,
        "fork_status": fork_status,
        "decision": decision,
        "reasons": reasons,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "Continuation is admissible only when the supplied intact head "
            "check is CURRENT and the supplied intact fork check is NO_FORK. "
            "NO_FORK does not establish currentness. This receipt does not "
            "choose a head, determine truth, mutate canonical state, or grant "
            "acceptance, write authority, or execution authority."
        ),
    }

    return {**body, "receipt_hash": stable_hash(body)}
