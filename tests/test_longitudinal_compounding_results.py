from pathlib import Path

from holosim.longitudinal_compounding_results import (
    build_longitudinal_compounding_result,
)


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_COMMIT = "d8f4f23"


def _result():
    return build_longitudinal_compounding_result(
        repository_root=ROOT,
        implementation_commit=IMPLEMENTATION_COMMIT,
    )


def test_result_is_bound_to_frozen_implementation():
    result = _result()

    assert result["implementation_commit"] == IMPLEMENTATION_COMMIT
    assert result["type"] == "longitudinal_compounding_experiment_result"
    assert result["version"] == 1


def test_strong_causal_targets_require_a_loss_loss_restoration_pattern():
    result = _result()

    targets = {
        target["target_id"]: target
        for target in result["targets"]
    }

    for target_id in result["strong_causal_pattern_targets"]:
        target = targets[target_id]

        baseline_matches = (
            target.get("A_matches_frozen_target") is True
            or target.get("A_matches_preexisting_reference") is True
        )

        assert baseline_matches
        assert target["B_targeted_loss"] is True
        assert target["C_targeted_loss"] is True
        assert target["D_restores"] is True
        assert target["information_preserved"] is True


def test_expected_applicable_targets_show_preregistered_pattern():
    result = _result()

    targets = {
        target["target_id"]: target
        for target in result["targets"]
    }

    assert set(result["strong_causal_pattern_targets"]) == {
        "historical-completion-reopen",
        "stale-dependency",
        "idx-dominance",
        "continuity-v1",
    }

    assert result["preregistered_prediction_supported"] is True

    for target_id in result["strong_causal_pattern_targets"]:
        target = targets[target_id]
        assert target["B_targeted_loss"] is True
        assert target["C_targeted_loss"] is True
        assert target["D_restores"] is True


def test_non_applicable_targets_are_not_forced_to_fail():
    result = _result()

    targets = {
        target["target_id"]: target
        for target in result["targets"]
    }

    assert targets["no-invention"]["classification"] == (
        "STRUCTURAL_ABLATION_NOT_APPLICABLE"
    )
    assert targets["no-invention"]["frozen_state_reproduced"] is True

    determinism = targets["byte-repeat-determinism"]
    assert determinism["classification"] == (
        "STRUCTURAL_ABLATION_NOT_APPLICABLE"
    )
    assert determinism["canonical_bytes_identical"] is True
    assert determinism["projection_identity_identical"] is True
    assert determinism["runtime_reducer_added"] is False


def test_nonsemantic_permutation_negative_control_is_preserved():
    result = _result()

    targets = {
        target["target_id"]: target
        for target in result["targets"]
    }

    control = targets["permutation-invariance-control"]

    assert control["classification"] == "NEGATIVE_CONTROL_PRESERVED"
    assert control["nonsemantic_permutation_preserved"] is True


def test_continuity_result_does_not_overclaim_resurrection():
    result = _result()

    continuity = next(
        target
        for target in result["targets"]
        if target["target_id"] == "continuity-v1"
    )

    assert continuity["classification"] == "SUPPORTS_PREDICTION_PARTIALLY"
    assert continuity["not_demonstrated"] == [
        "SUPERSEDED_STATE_RESURRECTION_CAUSED_BY_ABLATION"
    ]


def test_result_preserves_authority_boundary():
    result = _result()

    assert result["subjective_consciousness_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_result_is_deterministic():
    first = _result()
    second = _result()

    assert first == second
    assert first["result_hash"] == second["result_hash"]