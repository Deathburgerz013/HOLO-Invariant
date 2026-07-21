"""Deterministic, non-authoritative audit of an identified check and bound result."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.check_identity import (
    CheckIdentityError,
    bind_check_result,
    build_check_identity,
)

AUDIT_STATUS_VALID = "VALID"
AUDIT_STATUS_STALE = "STALE"
AUDIT_STATUS_UNJUSTIFIED = "UNJUSTIFIED"
AUDIT_STATUS_CONFLICTED = "CONFLICTED"
AUDIT_STATUS_BLOCKED = "BLOCKED"


class CheckAuditError(ValueError):
    """Raised when a supplied check package is structurally invalid or tampered."""


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CheckAuditError(f"{field} must be an object")
    return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckAuditError(f"{field} must be a non-empty string")
    return value


def _unique_texts(values: Sequence[str], field: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise CheckAuditError(f"{field} must be a sequence of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _require_text(value, field)
        if item in seen:
            raise CheckAuditError(f"duplicate {field}: {item}")
        seen.add(item)
        normalized.append(item)
    return normalized


def _verify_check_identity(check_identity: Mapping[str, Any]) -> dict[str, Any]:
    try:
        rebuilt = build_check_identity(
            check_id=check_identity["check_id"],
            check_type=check_identity["check_type"],
            subject=check_identity["subject"],
            reference_ids=check_identity["reference_ids"],
            scope=check_identity["scope"],
            evidence_references=check_identity["evidence_references"],
            rule_references=check_identity["rule_references"],
            input_state_hash=check_identity["input_state_hash"],
        )
    except (KeyError, CheckIdentityError) as exc:
        raise CheckAuditError(f"invalid check_identity: {exc}") from exc

    if dict(check_identity) != rebuilt:
        raise CheckAuditError("check_identity hash does not match content")
    return rebuilt


def _verify_result_binding(
    check_identity: Mapping[str, Any],
    result_binding: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        rebuilt = bind_check_result(
            check_identity=check_identity,
            result=result_binding["result"],
            output_state_hash=result_binding["output_state_hash"],
            justifier_reference=result_binding.get("justifier_reference"),
        )
    except (KeyError, CheckIdentityError) as exc:
        raise CheckAuditError(f"invalid result_binding: {exc}") from exc

    if dict(result_binding) != rebuilt:
        raise CheckAuditError("result_binding hash does not match content")
    if result_binding.get("check_identity_hash") != check_identity.get(
        "check_identity_hash"
    ):
        raise CheckAuditError("result_binding does not belong to check_identity")
    return rebuilt


def audit_check(
    *,
    audit_check_id: str,
    check_identity: Mapping[str, Any],
    result_binding: Mapping[str, Any],
    current_state_hash: str,
    available_reference_ids: Sequence[str],
    unresolved_conflicts: Sequence[str] = (),
) -> dict[str, Any]:
    """Audit one exact check package at one exact current bounded state.

    This is a check of a check. It verifies structural integrity and provenance,
    then classifies only whether the prior check package is currently usable under
    the supplied bounded references and state. It does not establish truth,
    acceptance, or write authority.
    """
    prior_identity = _verify_check_identity(
        _require_mapping(check_identity, "check_identity")
    )
    prior_binding = _verify_result_binding(
        prior_identity,
        _require_mapping(result_binding, "result_binding"),
    )
    current_hash = _require_text(current_state_hash, "current_state_hash")
    available = _unique_texts(available_reference_ids, "available_reference_id")
    conflicts = _unique_texts(unresolved_conflicts, "unresolved_conflict")

    required_references = list(
        dict.fromkeys(
            [
                *prior_identity["reference_ids"],
                *prior_identity["evidence_references"],
                *prior_identity["rule_references"],
            ]
        )
    )
    justifier = prior_binding.get("justifier_reference")
    if justifier is not None and justifier not in required_references:
        required_references.append(justifier)

    missing_references = [
        reference for reference in required_references if reference not in available
    ]

    if conflicts:
        status = AUDIT_STATUS_CONFLICTED
    elif missing_references:
        status = AUDIT_STATUS_BLOCKED
    elif justifier is None:
        status = AUDIT_STATUS_UNJUSTIFIED
    elif current_hash != prior_binding["output_state_hash"]:
        status = AUDIT_STATUS_STALE
    else:
        status = AUDIT_STATUS_VALID

    audit_identity = build_check_identity(
        check_id=audit_check_id,
        check_type="check_audit",
        subject={
            "audited_check_id": prior_identity["check_id"],
            "audited_check_identity_hash": prior_identity["check_identity_hash"],
            "audited_binding_hash": prior_binding["binding_hash"],
        },
        reference_ids=required_references,
        scope={
            "current_state_hash": current_hash,
            "available_reference_ids": list(available),
        },
        evidence_references=[
            prior_identity["check_identity_hash"],
            prior_binding["binding_hash"],
        ],
        rule_references=["check-audit-v1"],
        input_state_hash=prior_binding["binding_hash"],
    )

    audit_result = {
        "status": status,
        "audited_check_id": prior_identity["check_id"],
        "audited_check_identity_hash": prior_identity["check_identity_hash"],
        "audited_binding_hash": prior_binding["binding_hash"],
        "current_state_hash": current_hash,
        "prior_output_state_hash": prior_binding["output_state_hash"],
        "required_reference_ids": deepcopy(required_references),
        "missing_reference_ids": deepcopy(missing_references),
        "unresolved_conflicts": deepcopy(conflicts),
        "justifier_reference": justifier,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    audit_binding = bind_check_result(
        check_identity=audit_identity,
        result=audit_result,
        output_state_hash=current_hash,
        justifier_reference=None,
    )

    return {
        "audit_identity": audit_identity,
        "audit_result_binding": audit_binding,
    }
