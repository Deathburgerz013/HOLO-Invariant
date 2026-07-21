"""Deterministic comparison of independent observations over one exact baseline."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash

OBSERVATION_TYPE = "baseline_observation"
OBSERVATION_VERSION = 1
COMPARISON_TYPE = "baseline_observation_comparison"
COMPARISON_VERSION = 1

FINDING_SUPPORT = "SUPPORT"
FINDING_EXTENSION = "EXTENSION"
FINDING_CORRECTION = "CORRECTION"
FINDING_UNKNOWN = "UNKNOWN"
_ALLOWED_FINDINGS = {
    FINDING_SUPPORT,
    FINDING_EXTENSION,
    FINDING_CORRECTION,
    FINDING_UNKNOWN,
}

CLASS_AGREEMENT = "AGREEMENT"
CLASS_EXTENSION = "EXTENSION"
CLASS_CORRECTION = "CORRECTION"
CLASS_CONFLICT = "CONFLICT"
CLASS_UNKNOWN = "UNKNOWN"


class BaselineObservationError(ValueError):
    """Raised when an observation or comparison is invalid."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselineObservationError(f"{field} must be a non-empty string")
    return value


def _normalize_findings(findings: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(findings, Mapping) or not findings:
        raise BaselineObservationError("findings must be a non-empty object")
    normalized: dict[str, str] = {}
    for claim_id, status in findings.items():
        claim = _required_text(claim_id, "claim_id")
        state = _required_text(status, "finding_status")
        if state not in _ALLOWED_FINDINGS:
            raise BaselineObservationError(f"unsupported finding_status: {state}")
        normalized[claim] = state
    return dict(sorted(normalized.items()))


def build_baseline_observation(
    *,
    observer_id: str,
    baseline_id: str,
    baseline_state_hash: str,
    findings: Mapping[str, str],
) -> dict[str, Any]:
    """Record one observer's bounded reading of one exact baseline.

    The observation records only what the observer reports. It does not establish
    truth, acceptance, authority, or a next baseline.
    """
    body = {
        "type": OBSERVATION_TYPE,
        "version": OBSERVATION_VERSION,
        "observer_id": _required_text(observer_id, "observer_id"),
        "baseline_id": _required_text(baseline_id, "baseline_id"),
        "baseline_state_hash": _required_text(
            baseline_state_hash, "baseline_state_hash"
        ),
        "findings": _normalize_findings(findings),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        observation_id = stable_hash(body)
    except CanonicalValueError as exc:
        raise BaselineObservationError(str(exc)) from exc
    return {**body, "observation_id": observation_id}


def _verify_observation(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BaselineObservationError(f"{field} must be an observation object")
    try:
        rebuilt = build_baseline_observation(
            observer_id=value["observer_id"],
            baseline_id=value["baseline_id"],
            baseline_state_hash=value["baseline_state_hash"],
            findings=value["findings"],
        )
    except (KeyError, BaselineObservationError) as exc:
        raise BaselineObservationError(f"invalid {field}: {exc}") from exc
    if dict(value) != rebuilt:
        raise BaselineObservationError(f"{field} hash does not match content")
    return rebuilt


def _classify(left: str | None, right: str | None) -> str:
    states = {state for state in (left, right) if state is not None}
    if FINDING_UNKNOWN in states or len(states) == 1 and None in (left, right):
        return CLASS_UNKNOWN
    if left == FINDING_SUPPORT and right == FINDING_SUPPORT:
        return CLASS_AGREEMENT
    if left == FINDING_CORRECTION and right == FINDING_CORRECTION:
        return CLASS_CORRECTION
    if FINDING_CORRECTION in states and (
        FINDING_SUPPORT in states or FINDING_EXTENSION in states
    ):
        return CLASS_CONFLICT
    if FINDING_EXTENSION in states:
        return CLASS_EXTENSION
    return CLASS_UNKNOWN


def compare_baseline_observations(
    left_observation: Mapping[str, Any],
    right_observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two independently recorded observations of the same baseline.

    The comparison preserves agreement, extension, correction, conflict, and
    unknown distinctions. It does not vote, select a winner, or mutate baseline.
    """
    left = _verify_observation(left_observation, "left_observation")
    right = _verify_observation(right_observation, "right_observation")

    if left["baseline_id"] != right["baseline_id"]:
        raise BaselineObservationError("observations must reference the same baseline_id")
    if left["baseline_state_hash"] != right["baseline_state_hash"]:
        raise BaselineObservationError(
            "observations must reference the same baseline_state_hash"
        )
    if left["observer_id"] == right["observer_id"]:
        raise BaselineObservationError("comparison requires distinct observer_id values")

    claim_ids = sorted(set(left["findings"]) | set(right["findings"]))
    buckets = {
        CLASS_AGREEMENT: [],
        CLASS_EXTENSION: [],
        CLASS_CORRECTION: [],
        CLASS_CONFLICT: [],
        CLASS_UNKNOWN: [],
    }
    per_claim: dict[str, Any] = {}

    for claim_id in claim_ids:
        left_state = left["findings"].get(claim_id)
        right_state = right["findings"].get(claim_id)
        classification = _classify(left_state, right_state)
        entry = {
            "claim_id": claim_id,
            "left": left_state,
            "right": right_state,
            "classification": classification,
        }
        per_claim[claim_id] = entry
        buckets[classification].append(claim_id)

    payload = {
        "type": COMPARISON_TYPE,
        "version": COMPARISON_VERSION,
        "baseline_id": left["baseline_id"],
        "baseline_state_hash": left["baseline_state_hash"],
        "left_observation_id": left["observation_id"],
        "right_observation_id": right["observation_id"],
        "observer_ids": [left["observer_id"], right["observer_id"]],
        "per_claim": deepcopy(per_claim),
        "agreement": buckets[CLASS_AGREEMENT],
        "extension": buckets[CLASS_EXTENSION],
        "correction": buckets[CLASS_CORRECTION],
        "conflict": buckets[CLASS_CONFLICT],
        "unknown": buckets[CLASS_UNKNOWN],
        "next_baseline_selected": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    try:
        comparison_id = stable_hash(payload)
    except CanonicalValueError as exc:
        raise BaselineObservationError(str(exc)) from exc
    return {**payload, "comparison_id": comparison_id}
