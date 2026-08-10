"""Bounded, non-authoritative gate for proposing a next baseline."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash

GATE_TYPE = "baseline_promotion_gate"
GATE_VERSION = 1

STATUS_JUSTIFIED_TO_PROPOSE = "JUSTIFIED_TO_PROPOSE"
STATUS_BLOCKED = "BLOCKED"
STATUS_CONFLICTED = "CONFLICTED"
STATUS_INSUFFICIENT = "INSUFFICIENT"


class BaselinePromotionError(ValueError):
    """Raised when a baseline promotion gate input is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselinePromotionError(f"{field} must be a non-empty string")
    return value


def _verify_comparison(comparison: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(comparison, Mapping):
        raise BaselinePromotionError("comparison must be an object")
    expected_fields = {
        "type",
        "version",
        "baseline_id",
        "baseline_state_hash",
        "left_observation_id",
        "right_observation_id",
        "observer_ids",
        "per_claim",
        "agreement",
        "extension",
        "correction",
        "conflict",
        "unknown",
        "next_baseline_selected",
        "truth_claimed",
        "accepted",
        "write_authority",
        "comparison_id",
    }
    if set(comparison) != expected_fields:
        raise BaselinePromotionError(
            "comparison fields do not match the versioned schema"
        )
    body = {key: deepcopy(value) for key, value in comparison.items() if key != "comparison_id"}
    try:
        expected = stable_hash(body)
    except CanonicalValueError as exc:
        raise BaselinePromotionError(str(exc)) from exc
    if comparison["comparison_id"] != expected:
        raise BaselinePromotionError("comparison_id does not match comparison content")
    if comparison["type"] != "baseline_observation_comparison" or comparison["version"] != 1:
        raise BaselinePromotionError("unsupported comparison type or version")
    if comparison["next_baseline_selected"] is not False:
        raise BaselinePromotionError("comparison must not already select a next baseline")
    if comparison["truth_claimed"] is not False or comparison["accepted"] is not False:
        raise BaselinePromotionError("comparison must remain non-authoritative")
    if comparison["write_authority"] != "NONE":
        raise BaselinePromotionError("comparison must have write_authority NONE")
    return dict(comparison)


def evaluate_baseline_promotion(
    *,
    comparison: Mapping[str, Any],
    justification_references: Mapping[str, str],
) -> dict[str, Any]:
    """Evaluate whether a changed baseline is justified to propose, never to accept.

    Only EXTENSION and CORRECTION findings can motivate a candidate next baseline.
    Every motivating claim needs an explicit justification reference. CONFLICT blocks
    immediately; UNKNOWN or no motivating change is insufficient.
    """
    checked = _verify_comparison(comparison)
    if not isinstance(justification_references, Mapping):
        raise BaselinePromotionError("justification_references must be an object")

    normalized_refs: dict[str, str] = {}
    for claim_id, reference in justification_references.items():
        normalized_refs[_required_text(claim_id, "claim_id")] = _required_text(
            reference, "justification_reference"
        )
    normalized_refs = dict(sorted(normalized_refs.items()))

    motivating_claims = sorted(set(checked["extension"]) | set(checked["correction"]))
    missing_justifications = [
        claim_id for claim_id in motivating_claims if claim_id not in normalized_refs
    ]

    if checked["conflict"]:
        status = STATUS_CONFLICTED
    elif checked["unknown"] or not motivating_claims:
        status = STATUS_INSUFFICIENT
    elif missing_justifications:
        status = STATUS_BLOCKED
    else:
        status = STATUS_JUSTIFIED_TO_PROPOSE

    payload = {
        "type": GATE_TYPE,
        "version": GATE_VERSION,
        "baseline_id": checked["baseline_id"],
        "baseline_state_hash": checked["baseline_state_hash"],
        "comparison_id": checked["comparison_id"],
        "status": status,
        "motivating_claims": motivating_claims,
        "conflict_claims": list(checked["conflict"]),
        "unknown_claims": list(checked["unknown"]),
        "justification_references": normalized_refs,
        "missing_justifications": missing_justifications,
        "candidate_next_baseline_created": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        gate_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise BaselinePromotionError(str(exc)) from exc
    return {**payload, "gate_id": gate_id}
