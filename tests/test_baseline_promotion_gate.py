from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.baseline_observation_compare import (
    FINDING_CORRECTION,
    FINDING_EXTENSION,
    FINDING_SUPPORT,
    FINDING_UNKNOWN,
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import (
    BaselinePromotionError,
    STATUS_BLOCKED,
    STATUS_CONFLICTED,
    STATUS_INSUFFICIENT,
    STATUS_JUSTIFIED_TO_PROPOSE,
    evaluate_baseline_promotion,
)


def _comparison(left_findings, right_findings):
    left = build_baseline_observation(
        observer_id="observer-a",
        baseline_id="baseline-1",
        baseline_state_hash="state-1",
        findings=left_findings,
    )
    right = build_baseline_observation(
        observer_id="observer-b",
        baseline_id="baseline-1",
        baseline_state_hash="state-1",
        findings=right_findings,
    )
    return compare_baseline_observations(left, right)


def test_extension_with_justification_is_only_justified_to_propose():
    comparison = _comparison(
        {"claim-a": FINDING_EXTENSION},
        {"claim-a": FINDING_EXTENSION},
    )
    result = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={"claim-a": "justifier:claim-a:v1"},
    )

    assert result["status"] == STATUS_JUSTIFIED_TO_PROPOSE
    assert result["motivating_claims"] == ["claim-a"]
    assert result["candidate_next_baseline_created"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_correction_with_justification_is_justified_to_propose_not_accept():
    comparison = _comparison(
        {"claim-a": FINDING_CORRECTION},
        {"claim-a": FINDING_CORRECTION},
    )
    result = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={"claim-a": "justifier:correction:v1"},
    )

    assert result["status"] == STATUS_JUSTIFIED_TO_PROPOSE
    assert result["candidate_next_baseline_created"] is False
    assert result["accepted"] is False


def test_missing_justification_blocks_motivating_change():
    comparison = _comparison(
        {"claim-a": FINDING_EXTENSION},
        {"claim-a": FINDING_EXTENSION},
    )
    result = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={},
    )

    assert result["status"] == STATUS_BLOCKED
    assert result["missing_justifications"] == ["claim-a"]


def test_conflict_precedes_available_justification():
    comparison = _comparison(
        {"claim-a": FINDING_SUPPORT},
        {"claim-a": FINDING_CORRECTION},
    )
    result = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={"claim-a": "justifier:claim-a:v1"},
    )

    assert result["status"] == STATUS_CONFLICTED
    assert result["conflict_claims"] == ["claim-a"]


def test_unknown_is_insufficient_even_with_reference():
    comparison = _comparison(
        {"claim-a": FINDING_UNKNOWN},
        {"claim-a": FINDING_SUPPORT},
    )
    result = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={"claim-a": "justifier:claim-a:v1"},
    )

    assert result["status"] == STATUS_INSUFFICIENT
    assert result["unknown_claims"] == ["claim-a"]


def test_agreement_alone_does_not_motivate_new_baseline():
    comparison = _comparison(
        {"claim-a": FINDING_SUPPORT},
        {"claim-a": FINDING_SUPPORT},
    )
    result = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={},
    )

    assert result["status"] == STATUS_INSUFFICIENT
    assert result["motivating_claims"] == []


def test_tampered_comparison_fails_closed():
    comparison = _comparison(
        {"claim-a": FINDING_EXTENSION},
        {"claim-a": FINDING_EXTENSION},
    )
    tampered = deepcopy(comparison)
    tampered["baseline_state_hash"] = "tampered-state"

    with pytest.raises(BaselinePromotionError, match="comparison_id does not match"):
        evaluate_baseline_promotion(
            comparison=tampered,
            justification_references={"claim-a": "justifier:claim-a:v1"},
        )


def test_rehashed_comparison_with_undeclared_authority_field_fails_closed():
    comparison = _comparison(
        {"claim-a": FINDING_EXTENSION},
        {"claim-a": FINDING_EXTENSION},
    )
    forged = deepcopy(comparison)
    forged["approval"] = "GRANTED"
    body = {
        key: value
        for key, value in forged.items()
        if key != "comparison_id"
    }
    forged["comparison_id"] = stable_hash(body)

    with pytest.raises(BaselinePromotionError, match="schema"):
        evaluate_baseline_promotion(
            comparison=forged,
            justification_references={"claim-a": "justifier:claim-a:v1"},
        )
