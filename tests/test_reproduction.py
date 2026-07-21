from __future__ import annotations

import math

import pytest

from holosim.reproduction import ReproductionError, build_reproduction_check


def test_smaller_candidate_can_reproduce_same_explicit_outcomes() -> None:
    result = build_reproduction_check(
        "fixture@t0",
        baseline_substrate=[
            {"id": "core", "kind": "required"},
            {"id": "duplicate-note", "kind": "redundant"},
        ],
        candidate_substrate=[{"id": "core", "kind": "required"}],
        baseline_outcomes=[{"id": "behavior", "value": "stable"}],
        candidate_outcomes=[{"id": "behavior", "value": "stable"}],
    )

    assert result["status"] == "REPRODUCED"
    assert result["candidate_is_smaller"] is True
    assert result["removed_substrate_ids"] == ["duplicate-note"]
    assert result["removed_substrate_not_required_for_observed_reproduction"] == [
        "duplicate-note"
    ]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_changed_outcome_blocks_reproduction_claim() -> None:
    result = build_reproduction_check(
        "fixture@t1",
        baseline_substrate=[{"id": "core"}, {"id": "rule"}],
        candidate_substrate=[{"id": "core"}],
        baseline_outcomes=[{"id": "behavior", "value": "stable"}],
        candidate_outcomes=[{"id": "behavior", "value": "drifted"}],
    )

    assert result["status"] == "NOT_REPRODUCED"
    assert result["changed_outcomes"][0]["id"] == "behavior"
    assert result["removed_substrate_ids"] == ["rule"]
    assert result["removed_substrate_not_required_for_observed_reproduction"] == []


def test_missing_outcome_blocks_reproduction_claim() -> None:
    result = build_reproduction_check(
        "fixture@t2",
        baseline_substrate=[{"id": "core"}],
        candidate_substrate=[],
        baseline_outcomes=[{"id": "behavior"}, {"id": "recovery"}],
        candidate_outcomes=[{"id": "behavior"}],
    )

    assert result["status"] == "NOT_REPRODUCED"
    assert result["missing_outcome_ids"] == ["recovery"]


def test_added_candidate_outcome_does_not_erase_reproduced_baseline() -> None:
    result = build_reproduction_check(
        "fixture@t3",
        baseline_substrate=[{"id": "core"}],
        candidate_substrate=[{"id": "core"}],
        baseline_outcomes=[{"id": "behavior", "value": 1}],
        candidate_outcomes=[
            {"id": "behavior", "value": 1},
            {"id": "new-capability", "value": True},
        ],
    )

    assert result["status"] == "REPRODUCED"
    assert result["added_outcome_ids"] == ["new-capability"]
    assert result["candidate_is_smaller"] is False


def test_exact_outcome_identity_not_semantic_similarity() -> None:
    result = build_reproduction_check(
        "fixture@t4",
        baseline_substrate=[{"id": "core"}],
        candidate_substrate=[{"id": "core"}],
        baseline_outcomes=[{"id": "answer", "value": ["a", "b"]}],
        candidate_outcomes=[{"id": "answer", "value": ["b", "a"]}],
    )

    assert result["status"] == "NOT_REPRODUCED"
    assert result["changed_outcomes"][0]["id"] == "answer"


def test_duplicate_ids_fail_closed() -> None:
    with pytest.raises(ReproductionError, match="duplicate baseline_substrate id"):
        build_reproduction_check(
            "fixture@t5",
            baseline_substrate=[{"id": "x"}, {"id": "x"}],
            candidate_substrate=[],
            baseline_outcomes=[],
            candidate_outcomes=[],
        )


def test_nonfinite_values_fail_closed() -> None:
    with pytest.raises(ReproductionError, match="numbers must be finite"):
        build_reproduction_check(
            "fixture@t6",
            baseline_substrate=[{"id": "x", "score": math.inf}],
            candidate_substrate=[],
            baseline_outcomes=[],
            candidate_outcomes=[],
        )


def test_cyclic_values_fail_closed() -> None:
    cyclic: dict[str, object] = {"id": "x"}
    cyclic["self"] = cyclic

    with pytest.raises(ReproductionError, match="values must not contain cycles"):
        build_reproduction_check(
            "fixture@t7",
            baseline_substrate=[cyclic],
            candidate_substrate=[],
            baseline_outcomes=[],
            candidate_outcomes=[],
        )


def test_result_hash_is_deterministic() -> None:
    kwargs = {
        "reference": "fixture@t8",
        "baseline_substrate": [{"id": "b"}, {"id": "a"}],
        "candidate_substrate": [{"id": "a"}],
        "baseline_outcomes": [{"id": "result", "value": 1}],
        "candidate_outcomes": [{"id": "result", "value": 1}],
    }

    first = build_reproduction_check(**kwargs)
    second = build_reproduction_check(**kwargs)

    assert first == second
    assert len(first["reproduction_hash"]) == 64
