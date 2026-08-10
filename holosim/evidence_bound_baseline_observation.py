"""Bind baseline findings to exact, validated observation evidence.

Distinct result receipts prevent one identical observation from posing as two
observers.  Distinct receipts do not by themselves prove independent origin or
truth; the resulting comparison remains non-authoritative and may only justify
proposing a successor baseline.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.baseline_observation_compare import (
    BaselineObservationError,
    FINDING_UNKNOWN,
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import (
    BaselinePromotionError,
    evaluate_baseline_promotion,
)
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import (
    HookContractError,
    validate_hook_request,
    validate_hook_result,
)

BOUND_OBSERVATION_TYPE = "evidence_bound_baseline_observation"
BOUND_COMPARISON_TYPE = "evidence_bound_baseline_comparison"
BOUND_PROMOTION_TYPE = "evidence_bound_baseline_promotion"
BOUND_VERSION = 1

BOUND_OBSERVATION_FIELDS = {
    "type",
    "version",
    "request",
    "observation_result",
    "evidence_result_hash",
    "observation",
    "truth_claimed",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "binding_hash",
}

BOUND_COMPARISON_FIELDS = {
    "type",
    "version",
    "left_binding",
    "right_binding",
    "baseline_id",
    "baseline_state_hash",
    "evidence_result_hashes",
    "comparison",
    "truth_claimed",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "comparison_binding_hash",
}


class EvidenceBoundBaselineError(ValueError):
    """Raised when evidence cannot support the claimed bounded relationship."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise EvidenceBoundBaselineError(str(exc)) from exc


def _authority_is_none(value: Mapping[str, Any], field: str) -> None:
    if (
        value.get("truth_claimed") is not False
        or value.get("accepted") is not False
        or value.get("write_authority") != "NONE"
    ):
        raise EvidenceBoundBaselineError(f"{field} cannot grant authority")


def build_evidence_bound_baseline_observation(
    *,
    observer_id: str,
    baseline_id: str,
    baseline_state_hash: str,
    findings: Mapping[str, str],
    request: Mapping[str, Any],
    observation_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one baseline reading to the complete observation that informed it."""
    try:
        validate_hook_request(request)
        validate_hook_result(observation_result, request=request)
    except HookContractError as exc:
        raise EvidenceBoundBaselineError(f"observation evidence is invalid: {exc}") from exc

    if observation_result["status"] != "OBSERVED" and any(
        finding != FINDING_UNKNOWN for finding in findings.values()
    ):
        raise EvidenceBoundBaselineError(
            "failed or unavailable evidence may report only UNKNOWN findings"
        )

    try:
        observation = build_baseline_observation(
            observer_id=observer_id,
            baseline_id=baseline_id,
            baseline_state_hash=baseline_state_hash,
            findings=findings,
        )
    except BaselineObservationError as exc:
        raise EvidenceBoundBaselineError(str(exc)) from exc

    body = {
        "type": BOUND_OBSERVATION_TYPE,
        "version": BOUND_VERSION,
        "request": deepcopy(dict(request)),
        "observation_result": deepcopy(dict(observation_result)),
        "evidence_result_hash": observation_result["result_hash"],
        "observation": observation,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "The binding proves correspondence to one intact observation result only. "
            "It does not prove the finding true, accepted, authoritative, current, or "
            "independent from another source."
        ),
    }
    return {**body, "binding_hash": _hash(body)}


def validate_evidence_bound_baseline_observation(
    binding: Mapping[str, Any],
) -> bool:
    """Regenerate one evidence binding and require exact schema and identity."""
    if type(binding) is not dict:
        raise EvidenceBoundBaselineError("binding must be a plain dictionary")
    if set(binding) != BOUND_OBSERVATION_FIELDS:
        raise EvidenceBoundBaselineError(
            "binding fields do not match the versioned schema"
        )
    if (
        binding.get("type") != BOUND_OBSERVATION_TYPE
        or binding.get("version") != BOUND_VERSION
    ):
        raise EvidenceBoundBaselineError("binding type or version is invalid")
    _authority_is_none(binding, "binding")
    if type(binding.get("interpretation_notice")) is not str:
        raise EvidenceBoundBaselineError("interpretation_notice must be a string")

    observation = binding.get("observation")
    if not isinstance(observation, Mapping):
        raise EvidenceBoundBaselineError("observation must be an object")
    try:
        rebuilt = build_evidence_bound_baseline_observation(
            observer_id=observation["observer_id"],
            baseline_id=observation["baseline_id"],
            baseline_state_hash=observation["baseline_state_hash"],
            findings=observation["findings"],
            request=binding["request"],
            observation_result=binding["observation_result"],
        )
    except (KeyError, TypeError, EvidenceBoundBaselineError) as exc:
        if isinstance(exc, EvidenceBoundBaselineError):
            raise
        raise EvidenceBoundBaselineError("binding evidence is malformed") from exc
    if rebuilt != binding:
        raise EvidenceBoundBaselineError(
            "binding does not match its observation evidence"
        )
    return True


def compare_evidence_bound_baseline_observations(
    left_binding: Mapping[str, Any],
    right_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two evidence-bound findings without inferring source independence."""
    validate_evidence_bound_baseline_observation(left_binding)
    validate_evidence_bound_baseline_observation(right_binding)
    left_hash = left_binding["evidence_result_hash"]
    right_hash = right_binding["evidence_result_hash"]
    if left_hash == right_hash:
        raise EvidenceBoundBaselineError(
            "comparison requires distinct evidence result receipts"
        )
    try:
        comparison = compare_baseline_observations(
            left_binding["observation"],
            right_binding["observation"],
        )
    except BaselineObservationError as exc:
        raise EvidenceBoundBaselineError(str(exc)) from exc

    body = {
        "type": BOUND_COMPARISON_TYPE,
        "version": BOUND_VERSION,
        "left_binding": deepcopy(dict(left_binding)),
        "right_binding": deepcopy(dict(right_binding)),
        "baseline_id": comparison["baseline_id"],
        "baseline_state_hash": comparison["baseline_state_hash"],
        "evidence_result_hashes": sorted([left_hash, right_hash]),
        "comparison": comparison,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Distinct evidence receipts prevent duplicate evidence from counting twice. "
            "They do not establish independent origin, truth, or authority."
        ),
    }
    return {**body, "comparison_binding_hash": _hash(body)}


def _validate_bound_comparison(value: Mapping[str, Any]) -> dict[str, Any]:
    if type(value) is not dict:
        raise EvidenceBoundBaselineError("comparison must be a plain dictionary")
    if set(value) != BOUND_COMPARISON_FIELDS:
        raise EvidenceBoundBaselineError(
            "comparison fields do not match the versioned schema"
        )
    if (
        value.get("type") != BOUND_COMPARISON_TYPE
        or value.get("version") != BOUND_VERSION
    ):
        raise EvidenceBoundBaselineError("comparison type or version is invalid")
    _authority_is_none(value, "comparison")
    if type(value.get("interpretation_notice")) is not str:
        raise EvidenceBoundBaselineError("interpretation_notice must be a string")
    rebuilt = compare_evidence_bound_baseline_observations(
        value["left_binding"], value["right_binding"]
    )
    if rebuilt != value:
        raise EvidenceBoundBaselineError(
            "comparison does not match its evidence bindings"
        )
    return rebuilt


def evaluate_evidence_bound_baseline_promotion(
    *, comparison: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive justification references from exact evidence receipts and gate them."""
    checked = _validate_bound_comparison(comparison)
    underlying = checked["comparison"]
    motivating_claims = sorted(
        set(underlying["extension"]) | set(underlying["correction"])
    )
    evidence_hashes = list(checked["evidence_result_hashes"])
    references = {
        claim_id: "evidence-binding:"
        + _hash(
            {
                "claim_id": claim_id,
                "evidence_result_hashes": evidence_hashes,
            }
        )
        for claim_id in motivating_claims
    }
    try:
        gate = evaluate_baseline_promotion(
            comparison=underlying,
            justification_references=references,
        )
    except BaselinePromotionError as exc:
        raise EvidenceBoundBaselineError(str(exc)) from exc

    body = {
        "type": BOUND_PROMOTION_TYPE,
        "version": BOUND_VERSION,
        "comparison_binding_hash": checked["comparison_binding_hash"],
        "baseline_id": checked["baseline_id"],
        "baseline_state_hash": checked["baseline_state_hash"],
        "evidence_result_hashes": evidence_hashes,
        "gate": gate,
        "candidate_next_baseline_created": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Evidence-bound findings may justify proposing a successor baseline only. "
            "They do not prove truth, source independence, acceptance, or authority."
        ),
    }
    return {**body, "promotion_hash": _hash(body)}