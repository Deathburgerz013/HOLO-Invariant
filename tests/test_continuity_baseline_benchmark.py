from copy import deepcopy

import pytest

from holosim.continuity_baseline_benchmark import (
    ContinuityBaselineBenchmarkError,
    build_continuity_benchmark,
    compare_continuity_conditions,
    score_continuity_condition,
)


def _fixture():
    return build_continuity_benchmark(
        benchmark_id="continuity-baseline-1",
        latest_justified_claim_ids=["claim-current"],
        superseded_claim_ids=["claim-old"],
        uncertainty_claim_ids=["gap-unknown"],
        required_lineage_edges=[["claim-old", "claim-current"]],
        stale_continuation_must_block=True,
    )


def test_fixture_is_deterministic_and_non_authoritative():
    first = _fixture()
    second = _fixture()

    assert first == second
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"


def test_condition_passes_only_when_all_bounded_continuity_properties_are_preserved():
    result = score_continuity_condition(
        fixture=_fixture(),
        condition_id="holo-like-condition",
        recovered_claim_ids=["claim-current", "gap-unknown"],
        claimed_current_claim_ids=["claim-current"],
        preserved_uncertainty_claim_ids=["gap-unknown"],
        reconstructed_lineage_edges=[["claim-old", "claim-current"]],
        stale_continuation_decision="BLOCK",
    )

    assert result["metrics"] == {
        "latest_justified_recall": 1.0,
        "superseded_resurrection_count": 0,
        "uncertainty_recall": 1.0,
        "lineage_recall": 1.0,
        "stale_continuation_blocked": True,
        "passes_bounded_continuity_fixture": True,
    }
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_plain_persistence_can_retain_old_and_new_without_establishing_current_justification():
    result = score_continuity_condition(
        fixture=_fixture(),
        condition_id="plain-history",
        recovered_claim_ids=["claim-old", "claim-current", "gap-unknown"],
        claimed_current_claim_ids=["claim-old", "claim-current"],
        preserved_uncertainty_claim_ids=[],
        reconstructed_lineage_edges=[],
        stale_continuation_decision="UNKNOWN",
    )

    assert result["metrics"]["latest_justified_recall"] == 1.0
    assert result["metrics"]["superseded_resurrection_count"] == 1
    assert result["metrics"]["uncertainty_recall"] == 0.0
    assert result["metrics"]["lineage_recall"] == 0.0
    assert result["metrics"]["stale_continuation_blocked"] is False
    assert result["metrics"]["passes_bounded_continuity_fixture"] is False


def test_retrieval_that_finds_current_claim_but_loses_lineage_and_gate_still_fails_fixture():
    result = score_continuity_condition(
        fixture=_fixture(),
        condition_id="retrieval-only",
        recovered_claim_ids=["claim-current"],
        claimed_current_claim_ids=["claim-current"],
        preserved_uncertainty_claim_ids=[],
        reconstructed_lineage_edges=[],
        stale_continuation_decision="UNKNOWN",
    )

    assert result["metrics"]["latest_justified_recall"] == 1.0
    assert result["metrics"]["superseded_resurrection_count"] == 0
    assert result["metrics"]["passes_bounded_continuity_fixture"] is False


def test_comparison_reports_candidate_passes_where_baseline_does_not_without_claiming_truth():
    fixture = _fixture()
    baseline = score_continuity_condition(
        fixture=fixture,
        condition_id="plain-history",
        recovered_claim_ids=["claim-old", "claim-current"],
        claimed_current_claim_ids=["claim-old", "claim-current"],
        preserved_uncertainty_claim_ids=[],
        reconstructed_lineage_edges=[],
        stale_continuation_decision="UNKNOWN",
    )
    candidate = score_continuity_condition(
        fixture=fixture,
        condition_id="bounded-continuity",
        recovered_claim_ids=["claim-current", "gap-unknown"],
        claimed_current_claim_ids=["claim-current"],
        preserved_uncertainty_claim_ids=["gap-unknown"],
        reconstructed_lineage_edges=[["claim-old", "claim-current"]],
        stale_continuation_decision="BLOCK",
    )

    comparison = compare_continuity_conditions(baseline=baseline, candidate=candidate)

    assert comparison["candidate_passes_where_baseline_does_not"] is True
    assert comparison["delta"]["superseded_resurrection_count"] == -1
    assert comparison["delta"]["uncertainty_recall"] == 1.0
    assert comparison["delta"]["lineage_recall"] == 1.0
    assert comparison["truth_claimed"] is False
    assert comparison["accepted"] is False
    assert comparison["write_authority"] == "NONE"


def test_tampered_fixture_is_rejected():
    fixture = _fixture()
    tampered = deepcopy(fixture)
    tampered["latest_justified_claim_ids"] = ["different-current"]

    with pytest.raises(ContinuityBaselineBenchmarkError, match="fixture hash does not match content"):
        score_continuity_condition(
            fixture=tampered,
            condition_id="tampered",
            recovered_claim_ids=[],
            claimed_current_claim_ids=[],
            preserved_uncertainty_claim_ids=[],
            reconstructed_lineage_edges=[],
            stale_continuation_decision="UNKNOWN",
        )


def test_fixture_rejects_current_and_superseded_overlap():
    with pytest.raises(ContinuityBaselineBenchmarkError, match="must be disjoint"):
        build_continuity_benchmark(
            benchmark_id="bad-overlap",
            latest_justified_claim_ids=["same"],
            superseded_claim_ids=["same"],
            uncertainty_claim_ids=[],
            required_lineage_edges=[],
        )


def test_comparison_requires_exact_same_fixture():
    first_fixture = _fixture()
    second_fixture = build_continuity_benchmark(
        benchmark_id="continuity-baseline-1",
        latest_justified_claim_ids=["claim-current"],
        superseded_claim_ids=["claim-old"],
        uncertainty_claim_ids=[],
        required_lineage_edges=[["claim-old", "claim-current"]],
    )
    first = score_continuity_condition(
        fixture=first_fixture,
        condition_id="first",
        recovered_claim_ids=[],
        claimed_current_claim_ids=[],
        preserved_uncertainty_claim_ids=[],
        reconstructed_lineage_edges=[],
        stale_continuation_decision="UNKNOWN",
    )
    second = score_continuity_condition(
        fixture=second_fixture,
        condition_id="second",
        recovered_claim_ids=[],
        claimed_current_claim_ids=[],
        preserved_uncertainty_claim_ids=[],
        reconstructed_lineage_edges=[],
        stale_continuation_decision="UNKNOWN",
    )

    with pytest.raises(ContinuityBaselineBenchmarkError, match="fixture_hash must match"):
        compare_continuity_conditions(baseline=first, candidate=second)
