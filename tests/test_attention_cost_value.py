from __future__ import annotations

from holosim.attention_cost_value import evaluate_attention_candidate


def test_attention_candidate_earns_cycles_when_value_exceeds_cost() -> None:
    result = evaluate_attention_candidate(
        candidate_id="broken-truth-hash",
        value=8,
        cost=2,
        urgency=3,
        dependency_impact=4,
    )

    assert result["type"] == "holo_attention_decision"
    assert result["version"] == 1
    assert result["candidate_id"] == "broken-truth-hash"
    assert result["decision"] == "EARN_CYCLES"
    assert result["score"] == 13
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert isinstance(result["decision_hash"], str)
    assert len(result["decision_hash"]) == 64
import pytest

from holosim.attention_cost_value import AttentionCostValueError


def test_attention_candidate_defers_when_score_is_not_positive() -> None:
    result = evaluate_attention_candidate(
        candidate_id="low-value-check",
        value=1,
        cost=5,
        urgency=1,
        dependency_impact=1,
    )

    assert result["score"] == -2
    assert result["decision"] == "DEFER"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_attention_candidate_rejects_non_finite_inputs() -> None:
    with pytest.raises(
        AttentionCostValueError,
        match="value must be a finite number",
    ):
        evaluate_attention_candidate(
            candidate_id="invalid-value",
            value=float("nan"),
            cost=1,
            urgency=1,
            dependency_impact=1,
        )