"""Bounded reconstruction of a software-lineage transition from external evidence.

This module asks a narrower question than lineage reproduction:

    Can a later observer reconstruct the prior state, triggering difference,
    transition reason, and justified continuation result from persisted evidence
    alone?

It consumes an explicit lineage artifact and fails closed when evidence required for
that reconstruction is missing, internally inconsistent, or tampered with. It does
not infer truth, discover repository history, grant authority, or claim that the
fixture represents every software lineage.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import stable_hash

RECEIPT_TYPE = "software_lineage_reconstruction_receipt"
RECEIPT_VERSION = 1

_REQUIRED_LINEAGE_FIELDS = (
    "original_verified_head",
    "newer_verified_head",
    "binding",
    "before_environment_change",
    "after_environment_change",
    "observed_fracture",
    "reproduction_hash",
)


def _result(status: str, *, reasons: list[str], reconstruction: Mapping[str, Any] | None) -> dict[str, Any]:
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "status": status,
        "reasons": list(reasons),
        "reconstruction": deepcopy(dict(reconstruction)) if reconstruction is not None else None,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def reconstruct_software_lineage(lineage: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct one bounded causal lineage from an external lineage artifact.

    COMPLETE means the required evidence is present, hash-consistent, and supports
    the exact CURRENT -> STALE -> BLOCK transition encoded by the fixture.
    INCOMPLETE means required evidence is absent. INVALID means supplied evidence is
    present but internally inconsistent or tampered with.
    """
    if not isinstance(lineage, Mapping):
        return _result("INVALID", reasons=["lineage_not_mapping"], reconstruction=None)

    missing = [field for field in _REQUIRED_LINEAGE_FIELDS if field not in lineage]
    if missing:
        return _result(
            "INCOMPLETE",
            reasons=[f"missing_required_evidence:{field}" for field in missing],
            reconstruction=None,
        )

    supplied_hash = lineage.get("reproduction_hash")
    body = {key: deepcopy(value) for key, value in lineage.items() if key != "reproduction_hash"}
    if not isinstance(supplied_hash, str) or supplied_hash != stable_hash(body):
        return _result("INVALID", reasons=["lineage_hash_mismatch"], reconstruction=None)

    try:
        original = lineage["original_verified_head"]
        newer = lineage["newer_verified_head"]
        binding = lineage["binding"]
        before = lineage["before_environment_change"]
        after = lineage["after_environment_change"]

        original_idx = original["idx"]
        original_hash = original["head_hash"]
        original_state = original["state"]
        newer_idx = newer["idx"]
        newer_hash = newer["head_hash"]
        newer_state = newer["state"]
        origin_binding_idx = binding["originating_head_idx"]
        origin_binding_hash = binding["originating_head_hash"]
        before_status = before["head_check"]["status"]
        before_decision = before["gate"]["decision"]
        after_status = after["head_check"]["status"]
        after_reasons = after["head_check"]["reasons"]
        after_decision = after["gate"]["decision"]
    except (KeyError, TypeError):
        return _result("INCOMPLETE", reasons=["nested_required_evidence_missing"], reconstruction=None)

    inconsistencies: list[str] = []
    if origin_binding_idx != original_idx or origin_binding_hash != original_hash:
        inconsistencies.append("binding_origin_does_not_match_prior_state")
    if not isinstance(original_idx, int) or not isinstance(newer_idx, int) or newer_idx <= original_idx:
        inconsistencies.append("verified_head_did_not_advance")
    if original_hash == newer_hash:
        inconsistencies.append("verified_head_identity_did_not_change")
    if before_status != "CURRENT" or before_decision != "ALLOW":
        inconsistencies.append("prior_state_not_current_and_allowed")
    if after_status != "STALE":
        inconsistencies.append("resulting_state_not_stale")
    if "newer_verified_head_exists" not in after_reasons:
        inconsistencies.append("transition_reason_not_preserved")
    if after_decision != "BLOCK":
        inconsistencies.append("stale_continuation_not_blocked")

    if inconsistencies:
        return _result("INVALID", reasons=inconsistencies, reconstruction=None)

    reconstruction = {
        "prior_state": {
            "head_idx": original_idx,
            "head_hash": original_hash,
            "state": deepcopy(original_state),
            "status": before_status,
            "continuation": before_decision,
        },
        "triggering_difference": {
            "kind": "newer_verified_head",
            "from_head_idx": original_idx,
            "to_head_idx": newer_idx,
            "from_head_hash": original_hash,
            "to_head_hash": newer_hash,
            "new_state": deepcopy(newer_state),
        },
        "transition": {
            "from_status": before_status,
            "to_status": after_status,
            "reason": "newer_verified_head_exists",
        },
        "resulting_state": {
            "head_idx": newer_idx,
            "head_hash": newer_hash,
            "continuation_from_prior_handoff": after_decision,
        },
        "observed_fracture": lineage["observed_fracture"],
    }
    return _result("COMPLETE", reasons=[], reconstruction=reconstruction)
