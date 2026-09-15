"""Bounded, read-only classification of correction scope.

The classifier consumes an explicitly ordered hierarchy and explicit
observations for every declared level. It reports how high a correction is
currently evidenced to travel without applying a correction, inferring
dependencies, claiming truth, or granting authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from holosim.canonical import stable_hash


RECEIPT_TYPE = "bounded_correction_scope_receipt"
RECEIPT_VERSION = 1

CONTRADICTED = "CONTRADICTED"
PRESERVED = "PRESERVED"
UNAVAILABLE = "UNAVAILABLE"

NO_CORRECTION = "NO_CORRECTION"
LOCAL = "LOCAL"
PROPAGATE = "PROPAGATE"
ESCALATE = "ESCALATE"
UNRESOLVED = "UNRESOLVED"

_OBSERVATION_STATES = {
    CONTRADICTED,
    PRESERVED,
    UNAVAILABLE,
}
MAX_LEVELS = 256


class CorrectionScopeError(ValueError):
    """Raised when the declared correction boundary is invalid."""


def _validate_levels(levels: Sequence[str]) -> list[str]:
    if type(levels) not in {list, tuple}:
        raise CorrectionScopeError("levels must be a list or tuple")
    if len(levels) < 2:
        raise CorrectionScopeError(
            "at least two hierarchy levels are required"
        )
    if len(levels) > MAX_LEVELS:
        raise CorrectionScopeError(
            f"levels cannot exceed {MAX_LEVELS} entries"
        )

    normalized: list[str] = []
    for level_id in levels:
        if type(level_id) is not str or not level_id.strip():
            raise CorrectionScopeError(
                "level ids must be nonempty strings"
            )
        if level_id != level_id.strip():
            raise CorrectionScopeError(
                "level ids cannot contain outer whitespace"
            )
        normalized.append(level_id)

    if len(set(normalized)) != len(normalized):
        raise CorrectionScopeError("level ids must be unique")

    return normalized


def _validate_observations(
    *,
    levels: list[str],
    observations: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(observations, Mapping):
        raise CorrectionScopeError("observations must be a mapping")

    for level_id in observations:
        if type(level_id) is not str or not level_id.strip():
            raise CorrectionScopeError(
                "observation level ids must be nonempty strings"
            )

    if set(observations) != set(levels):
        raise CorrectionScopeError(
            "observations must match the declared hierarchy levels"
        )

    normalized: dict[str, str] = {}
    for level_id in levels:
        outcome = observations[level_id]
        if type(outcome) is not str or outcome not in _OBSERVATION_STATES:
            raise CorrectionScopeError(
                "observation states must be CONTRADICTED, "
                "PRESERVED, or UNAVAILABLE"
            )
        normalized[level_id] = outcome

    return normalized


def classify_correction_scope(
    *,
    levels: Sequence[str],
    observations: Mapping[str, str],
) -> dict[str, Any]:
    """Classify the highest correction scope supported by observations.

    Levels are ordered from lowest/local to highest/shared. An unavailable
    observation above the highest confirmed contradiction prevents a bounded
    scope claim. Unavailability below that contradiction does not erase the
    already observed higher-level contradiction.
    """

    checked_levels = _validate_levels(levels)
    checked_observations = _validate_observations(
        levels=checked_levels,
        observations=observations,
    )

    contradicted_levels = [
        level_id
        for level_id in checked_levels
        if checked_observations[level_id] == CONTRADICTED
    ]
    preserved_levels = [
        level_id
        for level_id in checked_levels
        if checked_observations[level_id] == PRESERVED
    ]
    unresolved_levels = [
        level_id
        for level_id in checked_levels
        if checked_observations[level_id] == UNAVAILABLE
    ]

    highest_confirmed_correction_level: str | None = None
    blocking_unavailable_levels: list[str] = []

    if not contradicted_levels:
        if unresolved_levels:
            scope = UNRESOLVED
            blocking_unavailable_levels = list(unresolved_levels)
        else:
            scope = NO_CORRECTION
    else:
        highest_confirmed_correction_level = contradicted_levels[-1]
        highest_index = checked_levels.index(
            highest_confirmed_correction_level
        )
        blocking_unavailable_levels = [
            level_id
            for level_id in checked_levels[highest_index + 1 :]
            if checked_observations[level_id] == UNAVAILABLE
        ]

        if highest_index == len(checked_levels) - 1:
            scope = ESCALATE
        elif blocking_unavailable_levels:
            scope = UNRESOLVED
        elif highest_index == 0:
            scope = LOCAL
        else:
            scope = PROPAGATE

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "levels": checked_levels,
        "observations": checked_observations,
        "contradicted_levels": contradicted_levels,
        "preserved_levels": preserved_levels,
        "unresolved_levels": unresolved_levels,
        "blocking_unavailable_levels": blocking_unavailable_levels,
        "highest_confirmed_correction_level": (
            highest_confirmed_correction_level
        ),
        "scope": scope,
        "scope_complete": scope != UNRESOLVED,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt classifies only the supplied hierarchy and "
            "observations. It does not infer dependencies, determine truth, "
            "choose or apply a correction, mutate canonical state, or grant "
            "acceptance, write authority, or execution authority."
        ),
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }