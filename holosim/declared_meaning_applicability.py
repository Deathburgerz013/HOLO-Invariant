"""Bounded applicability evaluation for explicitly declared meanings.

Multiple meanings for the same term may remain valid simultaneously.
Applicability is determined only from declared conditions. This module does
not infer meanings from prose, choose among ambiguous meanings, execute
functions, determine truth, mutate canonical state, or grant authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from holosim.canonical import stable_hash


RECEIPT_TYPE = "declared_meaning_applicability_receipt"
RECEIPT_VERSION = 1

RESOLVED = "RESOLVED"
MULTI_APPLICABLE = "MULTI_APPLICABLE"
UNRESOLVED = "UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS"

_MEANING_FIELDS = {"meaning_id", "conditions", "function"}


class DeclaredMeaningApplicabilityError(ValueError):
    """Raised when declared meaning applicability is invalid."""


def _required_identity(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise DeclaredMeaningApplicabilityError(
            f"{field} must be a nonempty string"
        )
    if value != value.strip():
        raise DeclaredMeaningApplicabilityError(
            f"{field} cannot contain outer whitespace"
        )
    return value


def _validate_conditions(
    conditions: Sequence[str],
    field: str,
) -> list[str]:
    if type(conditions) not in {list, tuple}:
        raise DeclaredMeaningApplicabilityError(
            f"{field} must be a list or tuple"
        )

    if not conditions:
        raise DeclaredMeaningApplicabilityError(
            "each meaning requires at least one applicability condition"
        )

    checked: list[str] = []
    for index, condition in enumerate(conditions):
        checked.append(
            _required_identity(
                condition,
                f"{field}[{index}]",
            )
        )

    if len(set(checked)) != len(checked):
        raise DeclaredMeaningApplicabilityError(
            f"{field} cannot contain duplicate conditions"
        )

    return checked


def _validate_meanings(
    meanings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if type(meanings) not in {list, tuple}:
        raise DeclaredMeaningApplicabilityError(
            "meanings must be a list or tuple"
        )

    checked: list[dict[str, Any]] = []
    seen_meaning_ids: set[str] = set()

    for index, meaning in enumerate(meanings):
        if not isinstance(meaning, Mapping):
            raise DeclaredMeaningApplicabilityError(
                f"meanings[{index}] must be a mapping"
            )

        if set(meaning) != _MEANING_FIELDS:
            raise DeclaredMeaningApplicabilityError(
                f"meanings[{index}] fields must be exactly "
                "meaning_id, conditions, and function"
            )

        meaning_id = _required_identity(
            meaning["meaning_id"],
            f"meanings[{index}].meaning_id",
        )
        function = _required_identity(
            meaning["function"],
            f"meanings[{index}].function",
        )
        conditions = _validate_conditions(
            meaning["conditions"],
            f"meanings[{index}].conditions",
        )

        if meaning_id in seen_meaning_ids:
            raise DeclaredMeaningApplicabilityError(
                "meaning ids must be unique"
            )
        seen_meaning_ids.add(meaning_id)

        checked.append(
            {
                "meaning_id": meaning_id,
                "conditions": conditions,
                "function": function,
            }
        )

    return checked


def _validate_observed_conditions(
    conditions: Sequence[str],
    field: str,
) -> list[str]:
    if type(conditions) not in {list, tuple}:
        raise DeclaredMeaningApplicabilityError(
            f"{field} must be a list or tuple"
        )

    checked: list[str] = []
    for index, condition in enumerate(conditions):
        checked.append(
            _required_identity(
                condition,
                f"{field}[{index}]",
            )
        )

    if len(set(checked)) != len(checked):
        raise DeclaredMeaningApplicabilityError(
            f"{field} cannot contain duplicate conditions"
        )

    return checked


def evaluate_declared_meanings(
    *,
    term: str,
    meanings: Sequence[Mapping[str, Any]],
    satisfied_conditions: Sequence[str],
    uncertain_conditions: Sequence[str] = (),
) -> dict[str, Any]:
    """Evaluate declared meanings without collapsing preserved alternatives."""

    checked_term = _required_identity(term, "term")
    checked_meanings = _validate_meanings(meanings)
    checked_satisfied = _validate_observed_conditions(
        satisfied_conditions,
        "satisfied_conditions",
    )
    checked_uncertain = _validate_observed_conditions(
        uncertain_conditions,
        "uncertain_conditions",
    )

    satisfied = set(checked_satisfied)
    uncertain = set(checked_uncertain)

    if satisfied & uncertain:
        raise DeclaredMeaningApplicabilityError(
            "conditions cannot be both satisfied and uncertain"
        )

    preserved_meaning_ids = [
        meaning["meaning_id"]
        for meaning in checked_meanings
    ]

    applicable_meaning_ids: list[str] = []
    applicable_functions: list[str] = []
    uncertain_meaning_ids: list[str] = []

    for meaning in checked_meanings:
        conditions = set(meaning["conditions"])

        if conditions <= satisfied:
            applicable_meaning_ids.append(meaning["meaning_id"])
            applicable_functions.append(meaning["function"])
        elif conditions & uncertain:
            uncertain_meaning_ids.append(meaning["meaning_id"])

    if uncertain_meaning_ids:
        status = AMBIGUOUS
    elif len(applicable_meaning_ids) > 1:
        status = MULTI_APPLICABLE
    elif len(applicable_meaning_ids) == 1:
        status = RESOLVED
    else:
        status = UNRESOLVED

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "term": checked_term,
        "meanings": checked_meanings,
        "satisfied_conditions": checked_satisfied,
        "uncertain_conditions": checked_uncertain,
        "preserved_meaning_ids": preserved_meaning_ids,
        "applicable_meaning_ids": applicable_meaning_ids,
        "uncertain_meaning_ids": uncertain_meaning_ids,
        "applicable_functions": applicable_functions,
        "status": status,
        "clarification_required": status == AMBIGUOUS,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt evaluates only explicitly declared meanings and "
            "conditions. Every meaning requires at least one explicit "
            "applicability condition. Alternate meanings remain preserved. "
            "The receipt does not infer meaning from prose, choose among "
            "unresolved meanings, execute declared functions, determine "
            "truth, mutate canonical state, or grant authority."
        ),
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }