
"""Bounded classification of reported decisions and supplied observations.

Inputs are caller-supplied. This module does not independently witness
attempts or effects, establish enforcement, or grant execution authority.
"""

from __future__ import annotations

from typing import Any


class ContinuityEffectObservationError(ValueError):
    """Invalid classification input."""


def evaluate_continuity_effect(
    *,
    reported_decision: str,
    effect_observed: bool,
    action_attempted: bool | None = None,
) -> dict[str, Any]:
    """Classify a reported decision against supplied observations."""

    if type(reported_decision) is not str or reported_decision not in {
        "ALLOW",
        "BLOCK",
    }:
        raise ContinuityEffectObservationError(
            "reported_decision must be ALLOW or BLOCK"
        )

    if type(effect_observed) is not bool:
        raise ContinuityEffectObservationError(
            "effect_observed must be a boolean"
        )

    if action_attempted is not None and type(action_attempted) is not bool:
        raise ContinuityEffectObservationError(
            "action_attempted must be a boolean or None"
        )

    if reported_decision == "BLOCK" and effect_observed:
        classification = "REPORTED_BLOCK_EFFECT_CONTRADICTION"
    elif reported_decision == "ALLOW" and effect_observed:
        classification = "EXECUTION_OBSERVED"
    elif action_attempted is False:
        classification = "NO_ATTEMPT_OBSERVED"
    elif action_attempted is True and reported_decision == "BLOCK":
        classification = "BLOCK_REPORTED_NO_EFFECT"
    elif action_attempted is True:
        classification = "ATTEMPT_NO_EFFECT"
    elif reported_decision == "BLOCK":
        classification = "BLOCK_REPORTED_EFFECT_UNOBSERVED"
    else:
        classification = "NO_EFFECT_OBSERVED"

    return {
        "type": "continuity_effect_classification",
        "version": 1,
        "reported_decision": reported_decision,
        "action_attempted": action_attempted,
        "effect_observed": effect_observed,
        "classification": classification,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
