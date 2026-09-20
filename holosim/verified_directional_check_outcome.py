"""Derive one directional outcome from verified declared-verifier execution.

Direction is derived only from an intact execution receipt, an exact result
binding for that execution result, and an explicit deterministic evaluation
rule. This contract does not establish truth, acceptance, execution authority,
or write authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


class VerifiedDirectionalCheckOutcomeError(ValueError):
    """Raised when verified evidence cannot establish a directional outcome."""


def _verify_hash(
    artifact: Mapping[str, Any],
    *,
    hash_field: str,
    label: str,
) -> str:
    if not isinstance(artifact, Mapping):
        raise VerifiedDirectionalCheckOutcomeError(
            f"{label} must be a mapping"
        )

    supplied_hash = artifact.get(hash_field)
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise VerifiedDirectionalCheckOutcomeError(
            f"{label} requires {hash_field}"
        )

    body = {
        key: value
        for key, value in artifact.items()
        if key != hash_field
    }

    try:
        expected_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise VerifiedDirectionalCheckOutcomeError(str(exc)) from exc

    if supplied_hash != expected_hash:
        raise VerifiedDirectionalCheckOutcomeError(
            f"{label} hash mismatch"
        )

    return supplied_hash


def build_verified_directional_check_outcome(
    *,
    execution_receipt: Mapping[str, Any],
    result_binding: Mapping[str, Any],
    evaluation_rule: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive one explicit direction from verified execution evidence."""

    receipt_hash = _verify_hash(
        execution_receipt,
        hash_field="receipt_hash",
        label="execution receipt",
    )
    result_binding_hash = _verify_hash(
        result_binding,
        hash_field="binding_hash",
        label="result binding",
    )

    if execution_receipt.get("type") != "declared_verifier_execution_receipt":
        raise VerifiedDirectionalCheckOutcomeError(
            "execution receipt type mismatch"
        )

    if result_binding.get("type") != "check_result_binding":
        raise VerifiedDirectionalCheckOutcomeError(
            "result binding type mismatch"
        )

    if execution_receipt.get("check_id") != result_binding.get("check_id"):
        raise VerifiedDirectionalCheckOutcomeError("check_id mismatch")

    if (
        execution_receipt.get("check_identity_hash")
        != result_binding.get("check_identity_hash")
    ):
        raise VerifiedDirectionalCheckOutcomeError(
            "check_identity_hash mismatch"
        )

    try:
        receipt_result_hash = stable_hash(execution_receipt.get("result"))
    except CanonicalValueError as exc:
        raise VerifiedDirectionalCheckOutcomeError(str(exc)) from exc

    if execution_receipt.get("result_hash") != receipt_result_hash:
        raise VerifiedDirectionalCheckOutcomeError(
            "execution receipt result hash mismatch"
        )

    if result_binding.get("result_hash") != receipt_result_hash:
        raise VerifiedDirectionalCheckOutcomeError(
            "result hash mismatch"
        )

    if result_binding.get("result") != execution_receipt.get("result"):
        raise VerifiedDirectionalCheckOutcomeError(
            "result content mismatch"
        )

    if not isinstance(evaluation_rule, Mapping):
        raise VerifiedDirectionalCheckOutcomeError(
            "evaluation_rule must be a mapping"
        )

    expected_fields = {
        "type",
        "expected_result",
        "match_outcome",
        "mismatch_outcome",
    }
    if set(evaluation_rule) != expected_fields:
        raise VerifiedDirectionalCheckOutcomeError(
            "evaluation_rule fields mismatch"
        )

    if evaluation_rule["type"] != "exact_result_match":
        raise VerifiedDirectionalCheckOutcomeError(
            "evaluation_rule type is unsupported"
        )

    allowed_outcomes = {"SUPPORTS", "CONTRADICTS", "UNKNOWN"}
    for field in ("match_outcome", "mismatch_outcome"):
        if evaluation_rule[field] not in allowed_outcomes:
            raise VerifiedDirectionalCheckOutcomeError(
                f"{field} is invalid"
            )

    matched = (
        execution_receipt["result"]
        == evaluation_rule["expected_result"]
    )
    outcome = (
        evaluation_rule["match_outcome"]
        if matched
        else evaluation_rule["mismatch_outcome"]
    )

    try:
        evaluation_rule_hash = stable_hash(dict(evaluation_rule))
    except CanonicalValueError as exc:
        raise VerifiedDirectionalCheckOutcomeError(str(exc)) from exc

    body = {
        "type": "verified_directional_check_outcome",
        "version": 1,
        "verifier_id": execution_receipt["verifier_id"],
        "check_id": execution_receipt["check_id"],
        "check_identity_hash": execution_receipt["check_identity_hash"],
        "execution_receipt_hash": receipt_hash,
        "result_binding_hash": result_binding_hash,
        "result_hash": receipt_result_hash,
        "evaluation_rule_hash": evaluation_rule_hash,
        "matched": matched,
        "outcome": outcome,
        "truth_claimed": False,
        "accepted": False,
        "execution_authority": "NONE",
        "write_authority": "NONE",
    }

    try:
        outcome_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise VerifiedDirectionalCheckOutcomeError(str(exc)) from exc

    return {**body, "outcome_hash": outcome_hash}
