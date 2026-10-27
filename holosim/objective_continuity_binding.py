
"""Bounded, non-authoritative objective continuity bindings.

Preserves declared objective identity across loop handoffs.
Does not verify environmental truth, evidence authenticity, objective
correctness, or completion of an objective.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash


class ObjectiveContinuityBindingError(ValueError):
    """Invalid objective or successor continuity binding."""


_OBJECTIVE_FIELDS = {
    "type",
    "version",
    "objective_id",
    "definition",
    "criteria",
    "truth_claimed",
    "accepted",
    "write_authority",
    "objective_hash",
}

_SUCCESSOR_FIELDS = {
    "type",
    "version",
    "objective_id",
    "objective_hash",
    "prior_loop_id",
    "next_loop_id",
    "prior_evidence_hash",
    "next_problem_id",
    "truth_claimed",
    "accepted",
    "write_authority",
    "successor_hash",
}


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ObjectiveContinuityBindingError(
            f"{field} must be a nonempty string"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ObjectiveContinuityBindingError(
            f"{field} must be a lowercase SHA-256 hex digest"
        )
    return value


def _hash(body: dict[str, Any]) -> str:
    try:
        return stable_hash(body)
    except (CanonicalValueError, TypeError, ValueError, RecursionError) as exc:
        raise ObjectiveContinuityBindingError(
            "binding is not canonical JSON"
        ) from exc


def _no_authority(value: dict[str, Any]) -> None:
    if (
        value.get("truth_claimed") is not False
        or value.get("accepted") is not False
        or value.get("write_authority") != "NONE"
    ):
        raise ObjectiveContinuityBindingError(
            "binding cannot grant truth or write authority"
        )


def build_objective_binding(
    *,
    objective_id: str,
    definition: str,
    criteria: list[str],
) -> dict[str, Any]:
    """Bind an objective identifier to its declared definition and criteria."""
    _text(objective_id, "objective_id")
    _text(definition, "definition")

    if type(criteria) is not list or not criteria:
        raise ObjectiveContinuityBindingError(
            "criteria must be a nonempty list"
        )

    checked_criteria = [
        _text(criterion, "criterion") for criterion in criteria
    ]

    if len(set(checked_criteria)) != len(checked_criteria):
        raise ObjectiveContinuityBindingError(
            "criteria must not contain duplicates"
        )

    body = {
        "type": "objective_continuity_binding",
        "version": 1,
        "objective_id": objective_id,
        "definition": definition,
        "criteria": checked_criteria,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "objective_hash": _hash(body)}


def validate_objective_binding(objective: Any) -> bool:
    """Validate the exact objective schema and recomputed identity."""
    if type(objective) is not dict or set(objective) != _OBJECTIVE_FIELDS:
        raise ObjectiveContinuityBindingError(
            "objective fields mismatch"
        )

    _no_authority(objective)

    expected = build_objective_binding(
        objective_id=objective["objective_id"],
        definition=objective["definition"],
        criteria=objective["criteria"],
    )

    if objective != expected:
        raise ObjectiveContinuityBindingError(
            "objective identity mismatch"
        )

    return True


def build_objective_successor(
    *,
    objective: dict[str, Any],
    prior_loop_id: str,
    next_loop_id: str,
    prior_evidence_hash: str,
    next_problem_id: str,
) -> dict[str, Any]:
    """Describe a proposed next loop under the unchanged objective."""
    validate_objective_binding(objective)

    prior = _text(prior_loop_id, "prior_loop_id")
    following = _text(next_loop_id, "next_loop_id")

    if prior == following:
        raise ObjectiveContinuityBindingError(
            "successor loop must differ from prior loop"
        )

    _sha256(prior_evidence_hash, "prior_evidence_hash")
    _text(next_problem_id, "next_problem_id")

    body = {
        "type": "objective_continuity_successor",
        "version": 1,
        "objective_id": objective["objective_id"],
        "objective_hash": objective["objective_hash"],
        "prior_loop_id": prior,
        "next_loop_id": following,
        "prior_evidence_hash": prior_evidence_hash,
        "next_problem_id": next_problem_id,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "successor_hash": _hash(body)}


def validate_objective_successor(
    successor: Any,
    *,
    objective: dict[str, Any],
) -> bool:
    """Verify a successor against an independently supplied objective."""
    validate_objective_binding(objective)

    if type(successor) is not dict or set(successor) != _SUCCESSOR_FIELDS:
        raise ObjectiveContinuityBindingError(
            "successor fields mismatch"
        )

    _no_authority(successor)

    expected = build_objective_successor(
        objective=objective,
        prior_loop_id=successor["prior_loop_id"],
        next_loop_id=successor["next_loop_id"],
        prior_evidence_hash=successor["prior_evidence_hash"],
        next_problem_id=successor["next_problem_id"],
    )

    if successor != expected:
        raise ObjectiveContinuityBindingError(
            "successor identity or objective mismatch"
        )

    return True
