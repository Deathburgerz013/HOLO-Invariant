"""Bounded validation marks and linked present-state rechecks.

A validation mark records what one identified check concluded at one bounded state.
A recheck never rewrites that historical mark. It audits the prior package against the
present bounded state, then emits a new identified mark linked to the old one.

The caller supplies the present verdict. This module records and relates that verdict;
it does not independently establish truth, acceptance, or write authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.check_audit import (
    AUDIT_STATUS_BLOCKED,
    AUDIT_STATUS_CONFLICTED,
    AUDIT_STATUS_STALE,
    AUDIT_STATUS_UNJUSTIFIED,
    AUDIT_STATUS_VALID,
    audit_check,
)
from holosim.check_identity import bind_check_result, build_check_identity

MARK_SUPPORTED = "SUPPORTED"
MARK_FALSIFIED = "FALSIFIED"
MARK_UNKNOWN = "UNKNOWN"
MARK_BLOCKED = "BLOCKED"
MARKS = frozenset({MARK_SUPPORTED, MARK_FALSIFIED, MARK_UNKNOWN, MARK_BLOCKED})

RELATION_PRESERVED = "PRESERVED"
RELATION_REVALIDATED = "REVALIDATED"
RELATION_CHANGED = "CHANGED"
RELATION_BLOCKED = "BLOCKED"
RELATION_CONFLICTED = "CONFLICTED"
RELATION_UNJUSTIFIED = "UNJUSTIFIED"


class ValidationMarkError(ValueError):
    """Raised when a validation mark or recheck request is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationMarkError(f"{field} must be a non-empty string")
    return value


def _mark(value: Any) -> str:
    normalized = _required_text(value, "mark")
    if normalized not in MARKS:
        raise ValidationMarkError(f"unsupported mark: {normalized}")
    return normalized


def build_validation_mark(
    *,
    check_id: str,
    subject: Mapping[str, Any],
    reference_ids: Sequence[str],
    scope: Mapping[str, Any],
    evidence_references: Sequence[str],
    rule_references: Sequence[str],
    input_state_hash: str,
    mark: str,
    output_state_hash: str,
    justifier_reference: str,
) -> dict[str, Any]:
    """Build one non-authoritative validation mark at one bounded state."""
    normalized_mark = _mark(mark)
    current_hash = _required_text(output_state_hash, "output_state_hash")
    justifier = _required_text(justifier_reference, "justifier_reference")

    identity = build_check_identity(
        check_id=check_id,
        check_type="validation_mark",
        subject=subject,
        reference_ids=reference_ids,
        scope=scope,
        evidence_references=evidence_references,
        rule_references=rule_references,
        input_state_hash=input_state_hash,
    )
    result = {
        "mark": normalized_mark,
        "checked_state_hash": current_hash,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    binding = bind_check_result(
        check_identity=identity,
        result=result,
        output_state_hash=current_hash,
        justifier_reference=justifier,
    )
    return {"check_identity": identity, "result_binding": binding}


def _prior_mark(result_binding: Mapping[str, Any]) -> str:
    result = result_binding.get("result")
    if not isinstance(result, Mapping):
        raise ValidationMarkError("prior result_binding requires result")
    try:
        return _mark(result["mark"])
    except KeyError as exc:
        raise ValidationMarkError("prior validation mark requires result.mark") from exc


def _relation(*, audit_status: str, prior_mark: str, current_mark: str) -> str:
    if audit_status == AUDIT_STATUS_CONFLICTED:
        return RELATION_CONFLICTED
    if audit_status == AUDIT_STATUS_BLOCKED:
        return RELATION_BLOCKED
    if audit_status == AUDIT_STATUS_UNJUSTIFIED:
        return RELATION_UNJUSTIFIED
    if current_mark != prior_mark:
        return RELATION_CHANGED
    if audit_status == AUDIT_STATUS_STALE:
        return RELATION_REVALIDATED
    if audit_status == AUDIT_STATUS_VALID:
        return RELATION_PRESERVED
    raise ValidationMarkError(f"unsupported audit status: {audit_status}")


def recheck_validation_mark(
    *,
    recheck_check_id: str,
    prior_check_identity: Mapping[str, Any],
    prior_result_binding: Mapping[str, Any],
    current_state_hash: str,
    available_reference_ids: Sequence[str],
    current_mark: str,
    current_output_state_hash: str,
    current_justifier_reference: str,
    unresolved_conflicts: Sequence[str] = (),
) -> dict[str, Any]:
    """Recheck one historical validation mark without mutating it.

    The prior package is first audited against the present bounded state. A new check
    identity and result binding are then emitted, linked by exact hashes to the prior
    identity and binding. `current_mark` is a caller-supplied verdict, not a truth claim
    made by this function.
    """
    current_hash = _required_text(current_state_hash, "current_state_hash")
    output_hash = _required_text(current_output_state_hash, "current_output_state_hash")
    justifier = _required_text(current_justifier_reference, "current_justifier_reference")
    normalized_current_mark = _mark(current_mark)
    normalized_prior_mark = _prior_mark(prior_result_binding)

    audit = audit_check(
        audit_check_id=f"{recheck_check_id}:prior-audit",
        check_identity=prior_check_identity,
        result_binding=prior_result_binding,
        current_state_hash=current_hash,
        available_reference_ids=available_reference_ids,
        unresolved_conflicts=unresolved_conflicts,
    )
    audit_result = audit["audit_result_binding"]["result"]
    audit_status = audit_result["status"]
    relation = _relation(
        audit_status=audit_status,
        prior_mark=normalized_prior_mark,
        current_mark=normalized_current_mark,
    )

    identity = build_check_identity(
        check_id=recheck_check_id,
        check_type="validation_mark_recheck",
        subject={
            "prior_check_id": prior_check_identity["check_id"],
            "prior_check_identity_hash": prior_check_identity["check_identity_hash"],
            "prior_binding_hash": prior_result_binding["binding_hash"],
        },
        reference_ids=list(prior_check_identity["reference_ids"]),
        scope={
            "current_state_hash": current_hash,
            "available_reference_ids": list(available_reference_ids),
        },
        evidence_references=[
            prior_check_identity["check_identity_hash"],
            prior_result_binding["binding_hash"],
            audit["audit_identity"]["check_identity_hash"],
            audit["audit_result_binding"]["binding_hash"],
        ],
        rule_references=["validation-mark-recheck-v1"],
        input_state_hash=prior_result_binding["binding_hash"],
    )
    result = {
        "prior_mark": normalized_prior_mark,
        "current_mark": normalized_current_mark,
        "prior_audit_status": audit_status,
        "relation": relation,
        "prior_check_identity_hash": prior_check_identity["check_identity_hash"],
        "prior_binding_hash": prior_result_binding["binding_hash"],
        "current_state_hash": current_hash,
        "current_output_state_hash": output_hash,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    binding = bind_check_result(
        check_identity=identity,
        result=result,
        output_state_hash=output_hash,
        justifier_reference=justifier,
    )

    return {
        "prior": {
            "check_identity": deepcopy(dict(prior_check_identity)),
            "result_binding": deepcopy(dict(prior_result_binding)),
        },
        "prior_audit": audit,
        "recheck_identity": identity,
        "recheck_result_binding": binding,
    }
