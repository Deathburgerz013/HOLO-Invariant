"""Deterministic dual-baseline breaker for structured invariant artifacts.

The breaker does not decide what is better. It checks whether a candidate
preserves the exact structured claims previously verified by both an immutable
anchor and an immediate parent. Human-readable expression may change without
changing classification when the structured claims remain identical.

This first boundary does not infer meaning from prose, execute candidate code,
repair failures, promote state, or grant authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import (
    CanonicalValueError,
    canonical_bytes,
    stable_hash,
)


ARTIFACT_TYPE = "bounded_invariant_artifact"
ARTIFACT_VERSION = 1
COMPARISON_TYPE = "bounded_invariant_breaker_receipt"
COMPARISON_VERSION = 1

IDENTICAL = "IDENTICAL"
EQUIVALENT_EXPRESSION = "EQUIVALENT_EXPRESSION"
DOWNGRADE = "DOWNGRADE"
CONTRADICTION = "CONTRADICTION"
UNKNOWN = "UNKNOWN"

MAX_CLAIMS = 256
MAX_ARTIFACT_BYTES = 1_000_000

ARTIFACT_FIELDS = {
    "type",
    "version",
    "artifact_id",
    "artifact_label",
    "contract_id",
    "contract_version",
    "claims",
    "expression",
    "provenance",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
}

RECEIPT_BODY_FIELDS = {
    "type",
    "version",
    "anchor",
    "parent",
    "candidate",
    "anchor_artifact_id",
    "parent_artifact_id",
    "candidate_artifact_id",
    "contract_id",
    "contract_version",
    "classification",
    "preserved_claim_ids",
    "missing_claim_ids",
    "contradictory_claim_ids",
    "added_claim_ids",
    "baseline_conflict_ids",
    "counterexample",
    "expression_changed",
    "candidate_smaller",
    "promotion_eligible",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "interpretation_notice",
}


class BoundedInvariantBreakerError(ValueError):
    """Raised when an artifact or breaker receipt violates its contract."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise BoundedInvariantBreakerError(str(exc)) from exc


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BoundedInvariantBreakerError(
            f"{field} must be a non-empty string"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise BoundedInvariantBreakerError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return text


def _exact_fields(
    value: Any,
    fields: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BoundedInvariantBreakerError(f"{label} must be an object")
    normalized = deepcopy(dict(value))
    missing = sorted(fields - set(normalized))
    extra = sorted(set(normalized) - fields)
    if missing:
        raise BoundedInvariantBreakerError(
            f"{label} is missing fields: " + ", ".join(missing)
        )
    if extra:
        raise BoundedInvariantBreakerError(
            f"{label} has unsupported fields: " + ", ".join(extra)
        )
    return normalized


def _claims(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise BoundedInvariantBreakerError(
            "claims must be a non-empty object"
        )
    if len(value) > MAX_CLAIMS:
        raise BoundedInvariantBreakerError(
            f"claims cannot exceed {MAX_CLAIMS} entries"
        )
    normalized: dict[str, Any] = {}
    for claim_id, claim_value in value.items():
        key = _required_text(claim_id, "claim_id")
        if key != key.strip():
            raise BoundedInvariantBreakerError(
                "claim_id cannot contain outer whitespace"
            )
        _hash(claim_value)
        normalized[key] = deepcopy(claim_value)
    return normalized


def _provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise BoundedInvariantBreakerError(
            "provenance must be a non-empty object"
        )
    normalized = deepcopy(dict(value))
    _hash(normalized)
    return normalized


def build_invariant_artifact(
    *,
    artifact_label: str,
    contract_id: str,
    contract_version: int,
    claims: Mapping[str, Any],
    expression: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one immutable structured-claim artifact."""
    label = _required_text(artifact_label, "artifact_label")
    normalized_contract_id = _required_text(contract_id, "contract_id")
    if not isinstance(contract_version, int) or isinstance(
        contract_version,
        bool,
    ) or contract_version < 1:
        raise BoundedInvariantBreakerError(
            "contract_version must be a positive integer"
        )
    normalized_expression = _required_text(expression, "expression")
    normalized_claims = _claims(claims)
    normalized_provenance = _provenance(provenance)

    body: dict[str, Any] = {
        "type": ARTIFACT_TYPE,
        "version": ARTIFACT_VERSION,
        "artifact_label": label,
        "contract_id": normalized_contract_id,
        "contract_version": contract_version,
        "claims": normalized_claims,
        "expression": normalized_expression,
        "provenance": normalized_provenance,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    if len(canonical_bytes(body)) > MAX_ARTIFACT_BYTES:
        raise BoundedInvariantBreakerError(
            f"artifact cannot exceed {MAX_ARTIFACT_BYTES} canonical bytes"
        )
    return {**body, "artifact_id": _hash(body)}


def verify_invariant_artifact(
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify exact artifact schema, semantics, boundaries, and identity."""
    violations: list[str] = []
    actual_id = (
        artifact.get("artifact_id")
        if isinstance(artifact, Mapping)
        else None
    )
    expected_id: str | None = None
    try:
        normalized = _exact_fields(
            artifact,
            ARTIFACT_FIELDS,
            "artifact",
        )
        if normalized["type"] != ARTIFACT_TYPE:
            raise BoundedInvariantBreakerError("artifact type is invalid")
        if normalized["version"] != ARTIFACT_VERSION:
            raise BoundedInvariantBreakerError("artifact version is invalid")
        _required_text(normalized["artifact_label"], "artifact_label")
        _required_text(normalized["contract_id"], "contract_id")
        if not isinstance(normalized["contract_version"], int) or isinstance(
            normalized["contract_version"],
            bool,
        ) or normalized["contract_version"] < 1:
            raise BoundedInvariantBreakerError(
                "contract_version must be a positive integer"
            )
        _claims(normalized["claims"])
        _required_text(normalized["expression"], "expression")
        _provenance(normalized["provenance"])
        if normalized["accepted"] is not False:
            raise BoundedInvariantBreakerError(
                "artifact must remain non-accepting"
            )
        if normalized["truth_claimed"] is not False:
            raise BoundedInvariantBreakerError(
                "artifact must remain non-truth-claiming"
            )
        if normalized["write_authority"] != "NONE" or normalized[
            "execution_authority"
        ] != "NONE":
            raise BoundedInvariantBreakerError(
                "artifact must carry no write or execution authority"
            )
        body = {
            key: deepcopy(value)
            for key, value in normalized.items()
            if key != "artifact_id"
        }
        if len(canonical_bytes(body)) > MAX_ARTIFACT_BYTES:
            raise BoundedInvariantBreakerError(
                f"artifact cannot exceed {MAX_ARTIFACT_BYTES} canonical bytes"
            )
        expected_id = _hash(body)
        _sha256(actual_id, "artifact_id")
        if actual_id != expected_id:
            raise BoundedInvariantBreakerError(
                "artifact identity mismatch"
            )
    except (BoundedInvariantBreakerError, CanonicalValueError) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "artifact_id": actual_id,
        "expected_artifact_id": expected_id,
        "violations": violations,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def _require_artifact(
    value: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    verification = verify_invariant_artifact(value)
    if not verification["valid"]:
        raise BoundedInvariantBreakerError(
            f"{label} is invalid: " + "; ".join(verification["violations"])
        )
    return deepcopy(dict(value))


def _first_counterexample(
    *,
    missing: list[str],
    contradictory: list[str],
    added: list[str],
    baseline_conflicts: list[str],
    anchor_claims: Mapping[str, Any],
    parent_claims: Mapping[str, Any],
    candidate_claims: Mapping[str, Any],
) -> dict[str, Any] | None:
    if baseline_conflicts:
        claim_id = baseline_conflicts[0]
        return {
            "kind": "BASELINE_CONFLICT",
            "claim_id": claim_id,
            "anchor": deepcopy(anchor_claims[claim_id]),
            "parent": deepcopy(parent_claims[claim_id]),
        }
    if contradictory:
        claim_id = contradictory[0]
        expected = (
            parent_claims[claim_id]
            if claim_id in parent_claims
            else anchor_claims[claim_id]
        )
        return {
            "kind": "CONTRADICTION",
            "claim_id": claim_id,
            "expected": deepcopy(expected),
            "candidate": deepcopy(candidate_claims[claim_id]),
        }
    if missing:
        claim_id = missing[0]
        expected = (
            parent_claims[claim_id]
            if claim_id in parent_claims
            else anchor_claims[claim_id]
        )
        return {
            "kind": "MISSING_CLAIM",
            "claim_id": claim_id,
            "expected": deepcopy(expected),
        }
    if added:
        claim_id = added[0]
        return {
            "kind": "UNVERIFIED_ADDITION",
            "claim_id": claim_id,
            "candidate": deepcopy(candidate_claims[claim_id]),
        }
    return None


def compare_invariant_artifacts(
    *,
    anchor: Mapping[str, Any],
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a candidate against immutable anchor and immediate parent."""
    normalized_anchor = _require_artifact(anchor, "anchor")
    normalized_parent = _require_artifact(parent, "parent")
    normalized_candidate = _require_artifact(candidate, "candidate")

    contracts = {
        (
            item["contract_id"],
            item["contract_version"],
        )
        for item in (
            normalized_anchor,
            normalized_parent,
            normalized_candidate,
        )
    }
    if len(contracts) != 1:
        raise BoundedInvariantBreakerError(
            "anchor, parent, and candidate must share one contract version"
        )

    anchor_claims = normalized_anchor["claims"]
    parent_claims = normalized_parent["claims"]
    candidate_claims = normalized_candidate["claims"]
    anchor_ids = set(anchor_claims)
    parent_ids = set(parent_claims)
    candidate_ids = set(candidate_claims)
    baseline_ids = anchor_ids | parent_ids

    baseline_conflicts = sorted(
        claim_id
        for claim_id in anchor_ids & parent_ids
        if anchor_claims[claim_id] != parent_claims[claim_id]
    )
    missing = sorted(baseline_ids - candidate_ids)
    contradictory = sorted(
        claim_id
        for claim_id in baseline_ids & candidate_ids
        if (
            claim_id in anchor_claims
            and candidate_claims[claim_id] != anchor_claims[claim_id]
        )
        or (
            claim_id in parent_claims
            and candidate_claims[claim_id] != parent_claims[claim_id]
        )
    )
    added = sorted(candidate_ids - baseline_ids)
    preserved = sorted(
        claim_id
        for claim_id in baseline_ids & candidate_ids
        if claim_id not in contradictory
    )

    if baseline_conflicts:
        classification = UNKNOWN
    elif contradictory:
        classification = CONTRADICTION
    elif missing:
        classification = DOWNGRADE
    elif added:
        classification = UNKNOWN
    elif normalized_candidate == normalized_parent:
        classification = IDENTICAL
    else:
        classification = EQUIVALENT_EXPRESSION

    counterexample = _first_counterexample(
        missing=missing,
        contradictory=contradictory,
        added=added,
        baseline_conflicts=baseline_conflicts,
        anchor_claims=anchor_claims,
        parent_claims=parent_claims,
        candidate_claims=candidate_claims,
    )
    expression_changed = (
        normalized_candidate["expression"]
        != normalized_parent["expression"]
    )
    candidate_smaller = len(
        canonical_bytes(normalized_candidate["expression"])
    ) < len(canonical_bytes(normalized_parent["expression"]))

    body: dict[str, Any] = {
        "type": COMPARISON_TYPE,
        "version": COMPARISON_VERSION,
        "anchor": normalized_anchor,
        "parent": normalized_parent,
        "candidate": normalized_candidate,
        "anchor_artifact_id": normalized_anchor["artifact_id"],
        "parent_artifact_id": normalized_parent["artifact_id"],
        "candidate_artifact_id": normalized_candidate["artifact_id"],
        "contract_id": normalized_anchor["contract_id"],
        "contract_version": normalized_anchor["contract_version"],
        "classification": classification,
        "preserved_claim_ids": preserved,
        "missing_claim_ids": missing,
        "contradictory_claim_ids": contradictory,
        "added_claim_ids": added,
        "baseline_conflict_ids": baseline_conflicts,
        "counterexample": counterexample,
        "expression_changed": expression_changed,
        "candidate_smaller": candidate_smaller,
        "promotion_eligible": classification in {
            IDENTICAL,
            EQUIVALENT_EXPRESSION,
        },
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "This receipt compares exact structured claims against an "
            "immutable anchor and immediate parent. Equivalent expression "
            "means the supplied structured claims were preserved; it does "
            "not prove that prose was interpreted correctly, that the "
            "candidate is better, or that promotion is authorized."
        ),
    }
    return {**body, "receipt_id": _hash(body)}


def verify_breaker_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute a breaker receipt from its three embedded artifacts."""
    violations: list[str] = []
    actual_id = (
        receipt.get("receipt_id")
        if isinstance(receipt, Mapping)
        else None
    )
    expected_id: str | None = None
    try:
        fields = RECEIPT_BODY_FIELDS | {"receipt_id"}
        normalized = _exact_fields(receipt, fields, "receipt")
        if normalized["type"] != COMPARISON_TYPE:
            raise BoundedInvariantBreakerError("receipt type is invalid")
        if normalized["version"] != COMPARISON_VERSION:
            raise BoundedInvariantBreakerError("receipt version is invalid")
        rebuilt = compare_invariant_artifacts(
            anchor=normalized["anchor"],
            parent=normalized["parent"],
            candidate=normalized["candidate"],
        )
        for field in RECEIPT_BODY_FIELDS:
            if normalized[field] != rebuilt[field]:
                raise BoundedInvariantBreakerError(
                    f"receipt field does not match recomputation: {field}"
                )
        expected_id = rebuilt["receipt_id"]
        _sha256(actual_id, "receipt_id")
        if actual_id != expected_id:
            raise BoundedInvariantBreakerError(
                "breaker receipt identity mismatch"
            )
    except (BoundedInvariantBreakerError, CanonicalValueError) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "receipt_id": actual_id,
        "expected_receipt_id": expected_id,
        "violations": violations,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
