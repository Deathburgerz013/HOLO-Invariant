from __future__ import annotations

import pytest

from holosim.bounded_correction_scope import (
    ESCALATE,
    LOCAL,
    NO_CORRECTION,
    PROPAGATE,
    UNRESOLVED,
    CorrectionScopeError,
    classify_correction_scope,
)


LEVELS = ("sensory", "domain", "invariant")


def test_lowest_confirmed_contradiction_stays_local() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "CONTRADICTED",
            "domain": "PRESERVED",
            "invariant": "PRESERVED",
        },
    )

    assert receipt["scope"] == LOCAL
    assert receipt["highest_confirmed_correction_level"] == "sensory"
    assert receipt["contradicted_levels"] == ["sensory"]
    assert receipt["blocking_unavailable_levels"] == []
    assert receipt["scope_complete"] is True


def test_middle_confirmed_contradiction_propagates() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "CONTRADICTED",
            "domain": "CONTRADICTED",
            "invariant": "PRESERVED",
        },
    )

    assert receipt["scope"] == PROPAGATE
    assert receipt["highest_confirmed_correction_level"] == "domain"
    assert receipt["contradicted_levels"] == ["sensory", "domain"]
    assert receipt["scope_complete"] is True


def test_highest_confirmed_contradiction_escalates() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "PRESERVED",
            "domain": "CONTRADICTED",
            "invariant": "CONTRADICTED",
        },
    )

    assert receipt["scope"] == ESCALATE
    assert receipt["highest_confirmed_correction_level"] == "invariant"
    assert receipt["scope_complete"] is True


def test_unavailable_level_above_contradiction_blocks_scope() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "CONTRADICTED",
            "domain": "PRESERVED",
            "invariant": "UNAVAILABLE",
        },
    )

    assert receipt["scope"] == UNRESOLVED
    assert receipt["highest_confirmed_correction_level"] == "sensory"
    assert receipt["blocking_unavailable_levels"] == ["invariant"]
    assert receipt["scope_complete"] is False


def test_higher_contradiction_overrides_lower_unavailability() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "UNAVAILABLE",
            "domain": "CONTRADICTED",
            "invariant": "PRESERVED",
        },
    )

    assert receipt["scope"] == PROPAGATE
    assert receipt["unresolved_levels"] == ["sensory"]
    assert receipt["blocking_unavailable_levels"] == []
    assert receipt["scope_complete"] is True


def test_all_preserved_requires_no_correction() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "PRESERVED",
            "domain": "PRESERVED",
            "invariant": "PRESERVED",
        },
    )

    assert receipt["scope"] == NO_CORRECTION
    assert receipt["highest_confirmed_correction_level"] is None
    assert receipt["contradicted_levels"] == []
    assert receipt["unresolved_levels"] == []
    assert receipt["scope_complete"] is True


def test_unavailable_without_contradiction_is_unresolved() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "PRESERVED",
            "domain": "UNAVAILABLE",
            "invariant": "PRESERVED",
        },
    )

    assert receipt["scope"] == UNRESOLVED
    assert receipt["highest_confirmed_correction_level"] is None
    assert receipt["blocking_unavailable_levels"] == ["domain"]
    assert receipt["scope_complete"] is False


def test_receipt_is_deterministic_across_input_container_order() -> None:
    first = classify_correction_scope(
        levels=("sensory", "domain", "invariant"),
        observations={
            "sensory": "CONTRADICTED",
            "domain": "PRESERVED",
            "invariant": "PRESERVED",
        },
    )
    second = classify_correction_scope(
        levels=["sensory", "domain", "invariant"],
        observations={
            "invariant": "PRESERVED",
            "sensory": "CONTRADICTED",
            "domain": "PRESERVED",
        },
    )

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_receipt_cannot_claim_authority_or_mutation() -> None:
    receipt = classify_correction_scope(
        levels=LEVELS,
        observations={
            "sensory": "CONTRADICTED",
            "domain": "PRESERVED",
            "invariant": "PRESERVED",
        },
    )

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["canonical_mutation"] is False


@pytest.mark.parametrize(
    "levels",
    [
        (),
        ("only",),
        "sensory",
    ],
)
def test_hierarchy_requires_at_least_two_declared_levels(
    levels,
) -> None:
    with pytest.raises(CorrectionScopeError):
        classify_correction_scope(
            levels=levels,
            observations={},
        )


@pytest.mark.parametrize(
    "levels",
    [
        ("sensory", "sensory"),
        ("", "invariant"),
        (" sensory", "invariant"),
        (1, "invariant"),
    ],
)
def test_level_identities_fail_closed(levels) -> None:
    with pytest.raises(CorrectionScopeError):
        classify_correction_scope(
            levels=levels,
            observations={
                level_id: "PRESERVED"
                for level_id in levels
            },
        )


def test_observations_must_match_declared_levels() -> None:
    with pytest.raises(
        CorrectionScopeError,
        match="observations must match",
    ):
        classify_correction_scope(
            levels=LEVELS,
            observations={
                "sensory": "PRESERVED",
                "domain": "PRESERVED",
            },
        )


@pytest.mark.parametrize(
    "outcome",
    [
        "contradicted",
        "UNKNOWN",
        "",
        True,
    ],
)
def test_observation_states_fail_closed(outcome) -> None:
    with pytest.raises(
        CorrectionScopeError,
        match="observation states",
    ):
        classify_correction_scope(
            levels=LEVELS,
            observations={
                "sensory": outcome,
                "domain": "PRESERVED",
                "invariant": "PRESERVED",
            },
        )


def test_inputs_are_not_mutated() -> None:
    levels = ["sensory", "domain", "invariant"]
    observations = {
        "sensory": "CONTRADICTED",
        "domain": "PRESERVED",
        "invariant": "PRESERVED",
    }
    original_levels = list(levels)
    original_observations = dict(observations)

    classify_correction_scope(
        levels=levels,
        observations=observations,
    )

    assert levels == original_levels
    assert observations == original_observations