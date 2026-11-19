
import pytest

from holosim.continuity_effect_observation import evaluate_continuity_effect


@pytest.mark.parametrize(
    "reported_decision,effect_observed,expected",
    [
        ("BLOCK", False, "BLOCK_REPORTED_EFFECT_UNOBSERVED"),
        ("BLOCK", True, "REPORTED_BLOCK_EFFECT_CONTRADICTION"),
        ("ALLOW", True, "EXECUTION_OBSERVED"),
        ("ALLOW", False, "NO_EFFECT_OBSERVED"),
    ],
)
def test_effect_observation(
    reported_decision,
    effect_observed,
    expected,
):
    result = evaluate_continuity_effect(
        reported_decision=reported_decision,
        effect_observed=effect_observed,
    )

    assert result["classification"] == expected
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

def test_forged_block_is_detected_by_independent_file_witness(tmp_path):
    target = tmp_path / "prohibited_effect.txt"

    # The candidate reports BLOCK but performs the prohibited action.
    reported_decision = "BLOCK"
    target.write_text("effect occurred", encoding="utf-8")

    # The test independently observes the actual filesystem state.
    effect_observed = target.exists()

    result = evaluate_continuity_effect(
        reported_decision=reported_decision,
        effect_observed=effect_observed,
    )

    assert effect_observed is True
    assert result["classification"] == "REPORTED_BLOCK_EFFECT_CONTRADICTION"


def test_block_without_effect_is_not_proof_of_enforcement(tmp_path):
    target = tmp_path / "prohibited_effect.txt"

    # No action is attempted. The candidate merely reports BLOCK.
    reported_decision = "BLOCK"

    effect_observed = target.exists()

    result = evaluate_continuity_effect(
        reported_decision=reported_decision,
        effect_observed=effect_observed,
    )

    assert effect_observed is False
    assert result["classification"] == "BLOCK_REPORTED_EFFECT_UNOBSERVED"

    # This is only classification consistency, not proof of enforcement.
    # The next version must track whether an action was attempted.

def test_block_without_attempt_is_not_confirmed():
    result = evaluate_continuity_effect(
        reported_decision="BLOCK",
        action_attempted=False,
        effect_observed=False,
    )

    assert result["classification"] == "NO_ATTEMPT_OBSERVED"
    assert result["accepted"] is False
    assert result["execution_authority"] == "NONE"

@pytest.mark.parametrize(
    "kwargs",
    [
        {"reported_decision": "UNKNOWN", "effect_observed": False},
        {"reported_decision": "BLOCK", "effect_observed": 0},
        {
            "reported_decision": "BLOCK",
            "effect_observed": False,
            "action_attempted": 1,
        },
    ],
)
def test_invalid_observation_inputs_fail_closed(kwargs):
    from holosim.continuity_effect_observation import (
        ContinuityEffectObservationError,
    )

    with pytest.raises(ContinuityEffectObservationError):
        evaluate_continuity_effect(**kwargs)


def test_attempted_block_without_effect_is_not_enforcement_proof():
    result = evaluate_continuity_effect(
        reported_decision="BLOCK",
        action_attempted=True,
        effect_observed=False,
    )

    assert result["classification"] == "BLOCK_REPORTED_NO_EFFECT"
    assert result["accepted"] is False
    assert result["execution_authority"] == "NONE"
