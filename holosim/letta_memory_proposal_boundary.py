"""Non-authoritative proposal boundary for Letta-style memory edits.

This module intentionally has no Letta dependency and exposes no memory-write
operation.  It preserves a complete, exact-schema edit event as an
observational proposal for separate verification and authorization.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


EDIT_TYPE = "letta_memory_edit"
EDIT_VERSION = 1
EDIT_OPERATION = "replace"
EDIT_FIELDS = {
    "type",
    "version",
    "edit_id",
    "agent_id",
    "block_id",
    "block_label",
    "operation",
    "prior_value_sha256",
    "proposed_value",
    "observed_at",
    "provenance",
}
PROPOSAL_TYPE = "letta_memory_edit_proposal"
PROPOSAL_VERSION = 1
PROPOSAL_FIELDS = {
    "type",
    "version",
    "source_edit",
    "source_edit_id",
    "agent_id",
    "block_id",
    "block_label",
    "operation",
    "prior_value_sha256",
    "proposed_value_sha256",
    "proposed_value",
    "provenance",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "interpretation_notice",
}


class LettaMemoryBoundaryError(ValueError):
    """Raised when a Letta memory edit crosses the proposal boundary."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise LettaMemoryBoundaryError(str(exc)) from exc


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LettaMemoryBoundaryError(
            f"{field} must be a non-empty string"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise LettaMemoryBoundaryError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return text


def _validate_edit(edit: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(edit, Mapping):
        raise LettaMemoryBoundaryError("memory edit must be an object")
    normalized = deepcopy(dict(edit))
    missing = sorted(EDIT_FIELDS - set(normalized))
    extra = sorted(set(normalized) - EDIT_FIELDS)
    if missing:
        raise LettaMemoryBoundaryError(
            "memory edit is missing fields: " + ", ".join(missing)
        )
    if extra:
        raise LettaMemoryBoundaryError(
            "memory edit has unsupported fields: " + ", ".join(extra)
        )
    if normalized["type"] != EDIT_TYPE:
        raise LettaMemoryBoundaryError("memory edit type is invalid")
    if normalized["version"] != EDIT_VERSION:
        raise LettaMemoryBoundaryError("memory edit version is invalid")
    if normalized["operation"] != EDIT_OPERATION:
        raise LettaMemoryBoundaryError(
            "memory edit operation must be replace"
        )
    for field in ("agent_id", "block_id", "block_label", "observed_at"):
        _required_text(normalized[field], field)
    if not isinstance(normalized["proposed_value"], str):
        raise LettaMemoryBoundaryError(
            "proposed_value must be a string"
        )
    _sha256(normalized["prior_value_sha256"], "prior_value_sha256")
    if not isinstance(normalized["provenance"], Mapping) or not normalized[
        "provenance"
    ]:
        raise LettaMemoryBoundaryError(
            "provenance must be a non-empty object"
        )
    _hash(normalized["provenance"])

    edit_id = _sha256(normalized["edit_id"], "edit_id")
    expected_id = _hash(
        {
            key: value
            for key, value in normalized.items()
            if key != "edit_id"
        }
    )
    if edit_id != expected_id:
        raise LettaMemoryBoundaryError("memory edit identity mismatch")
    return normalized


def create_memory_edit_proposal(
    *,
    edit: Mapping[str, Any],
    current_value: str,
) -> dict[str, Any]:
    """Bind one exact memory edit to current state without applying it."""
    normalized = _validate_edit(edit)
    if not isinstance(current_value, str):
        raise LettaMemoryBoundaryError("current_value must be a string")
    current_hash = _hash(current_value)
    if normalized["prior_value_sha256"] != current_hash:
        raise LettaMemoryBoundaryError(
            "memory edit is bound to a different current value"
        )

    body = {
        "type": PROPOSAL_TYPE,
        "version": PROPOSAL_VERSION,
        "source_edit": normalized,
        "source_edit_id": normalized["edit_id"],
        "agent_id": normalized["agent_id"],
        "block_id": normalized["block_id"],
        "block_label": normalized["block_label"],
        "operation": normalized["operation"],
        "prior_value_sha256": current_hash,
        "proposed_value_sha256": _hash(normalized["proposed_value"]),
        "proposed_value": normalized["proposed_value"],
        "provenance": deepcopy(dict(normalized["provenance"])),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "This receipt preserves a proposed memory edit only. It does "
            "not establish truth, accept the edit, mutate memory, or "
            "authorize a downstream write."
        ),
    }
    return {**body, "proposal_id": _hash(body)}


def verify_memory_edit_proposal(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify proposal identity and boundaries without applying the edit."""
    violations: list[str] = []
    actual_id = proposal.get("proposal_id") if isinstance(proposal, Mapping) else None
    expected_id = None
    try:
        if not isinstance(proposal, Mapping):
            raise LettaMemoryBoundaryError("proposal must be an object")
        missing = sorted(PROPOSAL_FIELDS - set(proposal))
        extra = sorted(set(proposal) - PROPOSAL_FIELDS - {"proposal_id"})
        if missing:
            raise LettaMemoryBoundaryError(
                "proposal is missing fields: " + ", ".join(missing)
            )
        if extra:
            raise LettaMemoryBoundaryError(
                "proposal has unsupported fields: " + ", ".join(extra)
            )
        source_edit = _validate_edit(proposal["source_edit"])
        if proposal["type"] != PROPOSAL_TYPE or proposal["version"] != PROPOSAL_VERSION:
            raise LettaMemoryBoundaryError(
                "proposal type or version is invalid"
            )
        if proposal["source_edit_id"] != source_edit["edit_id"]:
            raise LettaMemoryBoundaryError("source edit identity mismatch")
        if proposal["accepted"] is not False or proposal["truth_claimed"] is not False:
            raise LettaMemoryBoundaryError(
                "proposal must remain non-accepting and non-truth-claiming"
            )
        if proposal["write_authority"] != "NONE" or proposal[
            "execution_authority"
        ] != "NONE":
            raise LettaMemoryBoundaryError(
                "proposal must carry no write or execution authority"
            )
        for field in (
            "agent_id",
            "block_id",
            "block_label",
            "operation",
            "prior_value_sha256",
            "proposed_value",
            "provenance",
        ):
            if proposal[field] != source_edit[field]:
                raise LettaMemoryBoundaryError(
                    f"proposal field does not match source edit: {field}"
                )
        if proposal["proposed_value_sha256"] != _hash(
            proposal["proposed_value"]
        ):
            raise LettaMemoryBoundaryError(
                "proposed value identity mismatch"
            )
        body = {
            key: deepcopy(proposal[key])
            for key in PROPOSAL_FIELDS
        }
        expected_id = _hash(body)
        _sha256(actual_id, "proposal_id")
        if actual_id != expected_id:
            raise LettaMemoryBoundaryError("proposal identity mismatch")
    except (LettaMemoryBoundaryError, CanonicalValueError) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "proposal_id": actual_id,
        "expected_proposal_id": expected_id,
        "violations": violations,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }