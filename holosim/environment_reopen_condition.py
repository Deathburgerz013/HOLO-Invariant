"""Evaluate one declared environment reopen condition from bound hook evidence."""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import HookContractError, validate_hook_request, validate_hook_result

RECEIPT_TYPE = "environment_reopen_condition_receipt"
RECEIPT_VERSION = 1
VERIFY_ACTION = "verify-reopen-condition"
SATISFIED_FIELD = "condition_satisfied"


class EnvironmentReopenConditionError(ValueError):
    """Raised when reopen-condition evidence is invalid or inconsistent."""


def evaluate_environment_reopen_condition(
    *,
    condition_id: str,
    comparison_identity: Mapping[str, Any],
    request: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one declared condition without reopening or mutating anything."""
    if not isinstance(condition_id, str) or not condition_id.strip():
        raise EnvironmentReopenConditionError("condition_id must be a nonempty string")
    if not isinstance(comparison_identity, Mapping):
        raise EnvironmentReopenConditionError("comparison_identity must be a mapping")

    try:
        validate_hook_request(request)
        validate_hook_result(result, request=request)
    except HookContractError as exc:
        raise EnvironmentReopenConditionError(str(exc)) from exc

    if request["action"] != VERIFY_ACTION:
        raise EnvironmentReopenConditionError("hook request uses the wrong action")
    if request["reference"] != condition_id:
        raise EnvironmentReopenConditionError("hook request references the wrong condition")

    identity_hash = comparison_identity.get("check_identity_hash")
    if not isinstance(identity_hash, str) or not identity_hash:
        raise EnvironmentReopenConditionError("comparison identity requires check_identity_hash")

    try:
        expected_identity_hash = stable_hash(
            {k: v for k, v in comparison_identity.items() if k != "check_identity_hash"}
        )
    except CanonicalValueError as exc:
        raise EnvironmentReopenConditionError(str(exc)) from exc
    if identity_hash != expected_identity_hash:
        raise EnvironmentReopenConditionError("comparison identity hash mismatch")

    payload = request["payload"]
    if set(payload) != {"comparison_check_identity_hash"}:
        raise EnvironmentReopenConditionError("hook payload fields mismatch")
    if payload["comparison_check_identity_hash"] != identity_hash:
        raise EnvironmentReopenConditionError("hook request is bound to different comparison evidence")

    status = result["status"]
    evidence = result["evidence"]
    if status == "OBSERVED":
        if set(evidence) != {SATISFIED_FIELD}:
            raise EnvironmentReopenConditionError("observed evidence fields mismatch")
        if type(evidence[SATISFIED_FIELD]) is not bool:
            raise EnvironmentReopenConditionError("condition_satisfied must be a boolean")
        outcome = "SATISFIED" if evidence[SATISFIED_FIELD] else "NOT_SATISFIED"
    else:
        outcome = "UNKNOWN"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "condition_id": condition_id,
        "comparison_check_identity_hash": identity_hash,
        "request_hash": request["request_hash"],
        "result_hash": result["result_hash"],
        "hook_status": status,
        "outcome": outcome,
        "reopen_authorized": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt evaluates one declared reopen condition from bound evidence. "
            "It does not reopen an episode, establish global truth, or grant authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_environment_reopen_condition_receipt(
    receipt: Mapping[str, Any],
    *,
    condition_id: str,
    comparison_identity: Mapping[str, Any],
    request: Mapping[str, Any],
    result: Mapping[str, Any],
) -> bool:
    """Verify a receipt by regenerating it from the exact supplied evidence."""
    if type(receipt) is not dict:
        raise EnvironmentReopenConditionError("receipt must be a plain dictionary")

    expected = evaluate_environment_reopen_condition(
        condition_id=condition_id,
        comparison_identity=comparison_identity,
        request=request,
        result=result,
    )

    if set(receipt) != set(expected):
        raise EnvironmentReopenConditionError("receipt fields do not match")
    if receipt != expected:
        raise EnvironmentReopenConditionError(
            "receipt does not match supplied evidence"
        )
    return True
