"""Fail-closed continuation gate for continuity handoffs.

This module consumes a tamper-evident continuity-head binding check and permits
continuation only when that check is exactly CURRENT. STALE, INVALID, UNKNOWN,
or malformed checks are blocked. It does not discover the current head, decide
truth, or grant authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash

HEAD_CHECK_TYPE = "continuity_head_binding_check"
GATE_TYPE = "continuity_current_gate_decision"
GATE_VERSION = 1


class ContinuityCurrentGateError(RuntimeError):
    """Raised when continuation is attempted without a valid CURRENT check."""


def _validate_head_check(head_check: Mapping[str, Any]) -> str:
    if not isinstance(head_check, Mapping) or head_check.get("type") != HEAD_CHECK_TYPE:
        raise ContinuityCurrentGateError(
            "head_check must be a continuity head binding check"
        )

    stored_hash = head_check.get("check_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        raise ContinuityCurrentGateError("head_check requires check_hash")

    body = {
        key: deepcopy(value)
        for key, value in head_check.items()
        if key != "check_hash"
    }
    try:
        if stable_hash(body) != stored_hash:
            raise ContinuityCurrentGateError("head_check hash does not match content")
    except CanonicalValueError as exc:
        raise ContinuityCurrentGateError(str(exc)) from exc

    return stored_hash


def evaluate_continuity_current_gate(
    *,
    head_check: Mapping[str, Any],
) -> dict[str, Any]:
    """Return ALLOW only for an intact CURRENT head-binding check.

    All other recognized statuses fail closed as BLOCK. This decision is bounded
    to the supplied head check and carries no truth, acceptance, or write authority.
    """
    check_hash = _validate_head_check(head_check)
    status = head_check.get("status")

    if status == "CURRENT":
        decision = "ALLOW"
        reasons: list[str] = []
    elif status in {"STALE", "INVALID", "UNKNOWN"}:
        decision = "BLOCK"
        reasons = [f"continuity_head_status_{str(status).lower()}"]
    else:
        raise ContinuityCurrentGateError("head_check has unsupported status")

    payload = {
        "type": GATE_TYPE,
        "version": GATE_VERSION,
        "binding_id": head_check.get("binding_id"),
        "contract_id": head_check.get("contract_id"),
        "head_check_hash": check_hash,
        "head_status": status,
        "decision": decision,
        "reasons": reasons,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        decision_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ContinuityCurrentGateError(str(exc)) from exc
    return {**payload, "decision_hash": decision_hash}


def require_current_continuity(
    *,
    head_check: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless the supplied continuity head check is CURRENT.

    Callers place this immediately before continuation. The function raises on
    STALE, INVALID, UNKNOWN, malformed, or tampered input, so code after this call
    is reachable only after an intact CURRENT check.
    """
    decision = evaluate_continuity_current_gate(head_check=head_check)
    if decision["decision"] != "ALLOW":
        raise ContinuityCurrentGateError(
            "continuation blocked: " + ",".join(decision["reasons"])
        )
    return decision
