"""Bounded derivation of relative priority from intact upstream evaluations.

This module derives only a relative priority relation between two declared
candidates. A derivation requires an intact passing frame-relative criterion
evaluation and an intact applicable evidence-bound rule evaluation.

It does not select a candidate, execute an action, determine truth, accept a
candidate, mutate canonical state, or grant authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "bounded_priority_derivation_receipt"
RECEIPT_VERSION = 1

CRITERION_EVALUATION_TYPE = "frame_relative_criterion_evaluation"


class BoundedPriorityDerivationError(ValueError):
    """Raised when declared priority-derivation inputs are invalid."""


def _required_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedPriorityDerivationError(
            f"{field} must be a nonempty string"
        )
    if value != value.strip():
        raise BoundedPriorityDerivationError(
            f"{field} cannot contain outer whitespace"
        )
    return value


def _validate_hashed_evaluation(
    evaluation: Mapping[str, Any],
    *,
    expected_type: str | None,
    label: str,
) -> str:
    if not isinstance(evaluation, Mapping):
        raise BoundedPriorityDerivationError(
            f"{label} must be a mapping"
        )

    if expected_type is not None and evaluation.get("type") != expected_type:
        raise BoundedPriorityDerivationError(
            f"{label} has invalid type"
        )

    stored_hash = evaluation.get("evaluation_hash")
    if type(stored_hash) is not str or not stored_hash:
        raise BoundedPriorityDerivationError(
            f"{label} requires evaluation_hash"
        )

    body = {
        key: deepcopy(value)
        for key, value in evaluation.items()
        if key != "evaluation_hash"
    }

    try:
        if stable_hash(body) != stored_hash:
            raise BoundedPriorityDerivationError(
                f"{label} hash does not match content"
            )
    except CanonicalValueError as exc:
        raise BoundedPriorityDerivationError(str(exc)) from exc

    return stored_hash


def derive_bounded_priority(
    *,
    candidate_a_id: str,
    candidate_b_id: str,
    preferred_candidate_id: str,
    criterion_evaluation: Mapping[str, Any],
    rule_applicability: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive bounded relative priority without performing selection."""

    candidate_a = _required_text(candidate_a_id, "candidate_a_id")
    candidate_b = _required_text(candidate_b_id, "candidate_b_id")
    preferred = _required_text(
        preferred_candidate_id,
        "preferred_candidate_id",
    )

    if candidate_a == candidate_b:
        raise BoundedPriorityDerivationError(
            "compared candidates must be distinct"
        )

    if preferred not in {candidate_a, candidate_b}:
        raise BoundedPriorityDerivationError(
            "preferred candidate must be one of the compared candidates"
        )

    criterion_evaluation_hash = _validate_hashed_evaluation(
        criterion_evaluation,
        expected_type=CRITERION_EVALUATION_TYPE,
        label="criterion evaluation",
    )

    if criterion_evaluation.get("result") != "PASS":
        raise BoundedPriorityDerivationError(
            "criterion evaluation must PASS"
        )

    rule_applicability_hash = _validate_hashed_evaluation(
        rule_applicability,
        expected_type=None,
        label="rule applicability",
    )

    if rule_applicability.get("result") != "APPLICABLE":
        raise BoundedPriorityDerivationError(
            "rule must be APPLICABLE"
        )

    rule_id = _required_text(
        rule_applicability.get("rule_id"),
        "rule_applicability.rule_id",
    )

    relation = (
        "A_OVER_B"
        if preferred == candidate_a
        else "B_OVER_A"
    )

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "candidate_a_id": candidate_a,
        "candidate_b_id": candidate_b,
        "preferred_candidate_id": preferred,
        "relation": relation,
        "criterion_evaluation_hash": criterion_evaluation_hash,
        "rule_applicability_hash": rule_applicability_hash,
        "rule_id": rule_id,
        "selected_candidate_id": None,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt derives only a declared relative priority between "
            "two candidates from an intact passing criterion evaluation and "
            "an intact applicable rule evaluation. It does not select or "
            "accept a candidate, execute an action, determine truth, mutate "
            "canonical state, or grant authority."
        ),
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }