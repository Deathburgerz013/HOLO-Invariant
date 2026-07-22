"""Deterministic continuity-compliance contract for fresh model instances.

This module does not make a model remember, decide truth, or grant authority. It
checks whether a supplied instance handoff acknowledges and preserves the exact
bounded recall state it was given before continuing.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash

CONTRACT_TYPE = "continuity_compliance_contract"
CONTRACT_VERSION = 1
ATTESTATION_TYPE = "continuity_compliance_attestation"
ATTESTATION_VERSION = 1


class ContinuityComplianceError(ValueError):
    """Raised when a continuity contract or attestation is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContinuityComplianceError(f"{field} must be a non-empty string")
    return value


def _unique_texts(values: Sequence[str], field: str, *, allow_empty: bool = True) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ContinuityComplianceError(f"{field} must be a sequence of strings")
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _required_text(value, field)
        if text in seen:
            raise ContinuityComplianceError(f"{field} must not contain duplicates")
        seen.add(text)
        out.append(text)
    if not allow_empty and not out:
        raise ContinuityComplianceError(f"{field} must not be empty")
    return out


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ContinuityComplianceError(f"{field} must be a non-empty object")
    return value


def build_continuity_compliance_contract(
    *,
    contract_id: str,
    subject_id: str,
    recall_kernel: Mapping[str, Any],
    observed_required_fields: Sequence[str],
    authority_limits: Sequence[str],
    unresolved_gap_ids: Sequence[str],
    recheck_condition_ids: Sequence[str],
) -> dict[str, Any]:
    """Build one exact handoff contract for a fresh model instance.

    ``observed_required_fields`` must be keys present in ``recall_kernel``. Their
    requirement is bounded to prior falsification evidence; this function does not
    claim universal necessity.
    """
    contract = _required_text(contract_id, "contract_id")
    subject = _required_text(subject_id, "subject_id")
    kernel = dict(_require_mapping(recall_kernel, "recall_kernel"))
    required = _unique_texts(observed_required_fields, "observed_required_fields")
    missing = [field for field in required if field not in kernel]
    if missing:
        raise ContinuityComplianceError(
            "observed_required_fields missing from recall_kernel: " + ", ".join(missing)
        )

    body = {
        "type": CONTRACT_TYPE,
        "version": CONTRACT_VERSION,
        "contract_id": contract,
        "subject_id": subject,
        "recall_kernel": deepcopy(kernel),
        "recall_kernel_hash": stable_hash(kernel),
        "observed_required_fields": required,
        "authority_limits": _unique_texts(authority_limits, "authority_limits"),
        "unresolved_gap_ids": _unique_texts(unresolved_gap_ids, "unresolved_gap_ids"),
        "recheck_condition_ids": _unique_texts(recheck_condition_ids, "recheck_condition_ids"),
        "universal_requirement_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        contract_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise ContinuityComplianceError(str(exc)) from exc
    return {**body, "contract_hash": contract_hash}


def evaluate_continuity_attestation(
    *,
    contract: Mapping[str, Any],
    instance_id: str,
    recalled_kernel_hash: str,
    recalled_fields: Sequence[str],
    acknowledged_authority_limits: Sequence[str],
    acknowledged_unresolved_gap_ids: Sequence[str],
    acknowledged_recheck_condition_ids: Sequence[str],
) -> dict[str, Any]:
    """Evaluate whether one instance respected the exact supplied handoff contract.

    Compliance here means only that the instance attested to the same kernel hash,
    included every previously observed-required field, and acknowledged all supplied
    authority limits, unresolved gaps, and recheck conditions. It does not prove the
    model understood them, establish truth, or authorize action.
    """
    if not isinstance(contract, Mapping) or contract.get("type") != CONTRACT_TYPE:
        raise ContinuityComplianceError("contract must be a continuity compliance contract")
    stored_hash = contract.get("contract_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        raise ContinuityComplianceError("contract requires contract_hash")
    body = {key: deepcopy(value) for key, value in contract.items() if key != "contract_hash"}
    try:
        if stable_hash(body) != stored_hash:
            raise ContinuityComplianceError("contract hash does not match content")
    except CanonicalValueError as exc:
        raise ContinuityComplianceError(str(exc)) from exc

    instance = _required_text(instance_id, "instance_id")
    recalled_hash = _required_text(recalled_kernel_hash, "recalled_kernel_hash")
    fields = _unique_texts(recalled_fields, "recalled_fields")
    limits = _unique_texts(acknowledged_authority_limits, "acknowledged_authority_limits")
    gaps = _unique_texts(acknowledged_unresolved_gap_ids, "acknowledged_unresolved_gap_ids")
    rechecks = _unique_texts(
        acknowledged_recheck_condition_ids,
        "acknowledged_recheck_condition_ids",
    )

    required_fields = list(contract.get("observed_required_fields", []))
    missing_required_fields = [field for field in required_fields if field not in fields]
    missing_authority_limits = [
        value for value in contract.get("authority_limits", []) if value not in limits
    ]
    missing_unresolved_gaps = [
        value for value in contract.get("unresolved_gap_ids", []) if value not in gaps
    ]
    missing_recheck_conditions = [
        value for value in contract.get("recheck_condition_ids", []) if value not in rechecks
    ]
    kernel_hash_matches = recalled_hash == contract.get("recall_kernel_hash")

    reasons: list[str] = []
    if not kernel_hash_matches:
        reasons.append("recall_kernel_hash_mismatch")
    if missing_required_fields:
        reasons.append("observed_required_fields_missing")
    if missing_authority_limits:
        reasons.append("authority_limits_not_acknowledged")
    if missing_unresolved_gaps:
        reasons.append("unresolved_gaps_not_acknowledged")
    if missing_recheck_conditions:
        reasons.append("recheck_conditions_not_acknowledged")

    status = "COMPLIANT" if not reasons else "NONCOMPLIANT"
    payload = {
        "type": ATTESTATION_TYPE,
        "version": ATTESTATION_VERSION,
        "contract_id": contract["contract_id"],
        "contract_hash": stored_hash,
        "instance_id": instance,
        "status": status,
        "recalled_kernel_hash": recalled_hash,
        "kernel_hash_matches": kernel_hash_matches,
        "recalled_fields": fields,
        "missing_observed_required_fields": missing_required_fields,
        "missing_authority_limits": missing_authority_limits,
        "missing_unresolved_gap_ids": missing_unresolved_gaps,
        "missing_recheck_condition_ids": missing_recheck_conditions,
        "noncompliance_reasons": reasons,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        attestation_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise ContinuityComplianceError(str(exc)) from exc
    return {**payload, "attestation_hash": attestation_hash}
