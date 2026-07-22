"""Bind a continuity handoff to the chain state it came from.

This module distinguishes an internally valid continuity contract from one that is
still current relative to a caller-supplied verified chain head. It does not decide
truth, infer the latest head, or grant authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash

BINDING_TYPE = "continuity_head_binding"
BINDING_VERSION = 1
CHECK_TYPE = "continuity_head_binding_check"
CHECK_VERSION = 1
CONTRACT_TYPE = "continuity_compliance_contract"


class ContinuityHeadBindingError(ValueError):
    """Raised when a continuity-head binding or referenced contract is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContinuityHeadBindingError(f"{field} must be a non-empty string")
    return value


def _required_index(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContinuityHeadBindingError(f"{field} must be a positive integer")
    return value


def _validate_contract(contract: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(contract, Mapping) or contract.get("type") != CONTRACT_TYPE:
        raise ContinuityHeadBindingError("contract must be a continuity compliance contract")

    stored_hash = contract.get("contract_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        raise ContinuityHeadBindingError("contract requires contract_hash")

    body = {key: deepcopy(value) for key, value in contract.items() if key != "contract_hash"}
    try:
        if stable_hash(body) != stored_hash:
            raise ContinuityHeadBindingError("contract hash does not match content")
    except CanonicalValueError as exc:
        raise ContinuityHeadBindingError(str(exc)) from exc

    subject_id = _required_text(contract.get("subject_id"), "contract.subject_id")
    return stored_hash, subject_id


def build_continuity_head_binding(
    *,
    binding_id: str,
    contract: Mapping[str, Any],
    originating_head_hash: str,
    originating_head_idx: int,
) -> dict[str, Any]:
    """Bind one exact continuity contract to the verified head it was derived from.

    The caller is responsible for supplying a head that was independently verified.
    This function records that reference; it does not discover or certify the head.
    """
    binding = _required_text(binding_id, "binding_id")
    contract_hash, subject_id = _validate_contract(contract)
    head_hash = _required_text(originating_head_hash, "originating_head_hash")
    head_idx = _required_index(originating_head_idx, "originating_head_idx")

    body = {
        "type": BINDING_TYPE,
        "version": BINDING_VERSION,
        "binding_id": binding,
        "contract_id": contract["contract_id"],
        "contract_hash": contract_hash,
        "subject_id": subject_id,
        "originating_head_hash": head_hash,
        "originating_head_idx": head_idx,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        binding_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise ContinuityHeadBindingError(str(exc)) from exc
    return {**body, "binding_hash": binding_hash}


def evaluate_continuity_head_binding(
    *,
    binding: Mapping[str, Any],
    contract: Mapping[str, Any],
    current_head_hash: str | None,
    current_head_idx: int | None,
) -> dict[str, Any]:
    """Classify whether a bound continuity contract is CURRENT, STALE, INVALID, or UNKNOWN.

    ``current_head_hash`` and ``current_head_idx`` must come from an external verified
    chain observation. Matching head identity means CURRENT. A strictly newer head means
    STALE. Contradictory identity at the same index, or a broken binding/contract link,
    means INVALID. Missing or older current-head information means UNKNOWN.
    """
    if not isinstance(binding, Mapping) or binding.get("type") != BINDING_TYPE:
        raise ContinuityHeadBindingError("binding must be a continuity head binding")

    stored_binding_hash = binding.get("binding_hash")
    if not isinstance(stored_binding_hash, str) or not stored_binding_hash:
        raise ContinuityHeadBindingError("binding requires binding_hash")

    body = {key: deepcopy(value) for key, value in binding.items() if key != "binding_hash"}
    try:
        if stable_hash(body) != stored_binding_hash:
            raise ContinuityHeadBindingError("binding hash does not match content")
    except CanonicalValueError as exc:
        raise ContinuityHeadBindingError(str(exc)) from exc

    contract_hash, subject_id = _validate_contract(contract)
    link_valid = (
        binding.get("contract_id") == contract.get("contract_id")
        and binding.get("contract_hash") == contract_hash
        and binding.get("subject_id") == subject_id
    )

    originating_hash = _required_text(binding.get("originating_head_hash"), "originating_head_hash")
    originating_idx = _required_index(binding.get("originating_head_idx"), "originating_head_idx")

    reasons: list[str] = []
    if not link_valid:
        status = "INVALID"
        reasons.append("contract_binding_mismatch")
    elif current_head_hash is None or current_head_idx is None:
        status = "UNKNOWN"
        reasons.append("current_head_unavailable")
    else:
        current_hash = _required_text(current_head_hash, "current_head_hash")
        current_idx = _required_index(current_head_idx, "current_head_idx")
        if current_idx < originating_idx:
            status = "UNKNOWN"
            reasons.append("current_head_precedes_origin")
        elif current_idx == originating_idx:
            if current_hash == originating_hash:
                status = "CURRENT"
            else:
                status = "INVALID"
                reasons.append("same_index_head_hash_mismatch")
        else:
            status = "STALE"
            reasons.append("newer_verified_head_exists")

    payload = {
        "type": CHECK_TYPE,
        "version": CHECK_VERSION,
        "binding_id": binding["binding_id"],
        "binding_hash": stored_binding_hash,
        "contract_id": binding["contract_id"],
        "contract_hash": binding["contract_hash"],
        "status": status,
        "originating_head_hash": originating_hash,
        "originating_head_idx": originating_idx,
        "current_head_hash": current_head_hash,
        "current_head_idx": current_head_idx,
        "reasons": reasons,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        check_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ContinuityHeadBindingError(str(exc)) from exc
    return {**payload, "check_hash": check_hash}
