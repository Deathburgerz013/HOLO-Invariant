from copy import deepcopy

import pytest

from holosim.environment_completion_evaluator import (
    CERTIFICATE_TYPE,
    CERTIFICATE_VERSION,
    CompletionEvaluationError,
    evaluate_completion,
)
from holosim.environment_snapshot import build_snapshot
from holosim.environment_snapshot_comparator import compare_snapshots


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64
EVIDENCE_C = "c" * 64


def snapshot_kwargs(index):
    return {
        "episode_id": "episode:camera-1",
        "environment_id": "environment:lab",
        "check_id": "check:stability:v1",
        "check_purpose": "Observe bounded environmental change.",
        "goal_reference": "goal:evaluate-completion-eligibility",
        "observer_ids": ["observer:camera-north", "tool:frame-reader:v1"],
        "clock_id": "clock:camera-north:v1",
        "observed_at": f"2026-07-14T23:3{index}:00Z",
        "feature_schema_id": "schema:camera-motion:v1",
        "observed": {"motion_score": index / 100, "frame": 40 + index},
        "missing": [],
        "unknown": [],
        "assumptions": [{"claim": "camera clock is calibrated"}],
        "falsifiers": [{"check": "compare independent camera"}],
        "evidence_sha256": [[EVIDENCE_A, EVIDENCE_B, EVIDENCE_C][index]],
        "provenance": {
            "source_id": f"video-loop:frame-{40 + index}",
            "tool_id": "frame-reader:v1",
        },
        "uncertainty": [],
    }


def window():
    snapshots = [build_snapshot(**snapshot_kwargs(index)) for index in range(3)]
    comparisons = [
        compare_snapshots(before, after)
        for before, after in zip(snapshots, snapshots[1:])
    ]
    return snapshots, comparisons


def contract():
    return {
        "feature_schema_id": "schema:camera-motion:v1",
        "distance_metric_id": "metric:normalized-motion:v1",
        "epsilon": 0.1,
        "coverage_measure_id": "coverage:required-surfaces:v1",
        "coverage_min": 0.9,
        "stable_count_min": 2,
        "observation_count_min": 3,
        "sampling_policy_id": "sampling:one-minute:v1",
        "required_signal_schema_id": "signals:camera-motion:v1",
    }


def measurements(comparisons):
    return {
        "comparison_distances": {
            comparison["comparison_id"]: 0.05 for comparison in comparisons
        },
        "observed_coverage": 1.0,
        "unresolved_required_signals": [],
        "sampling_window_valid": True,
        "provenance_check_passed": True,
        "uncertainty_within_bounds": True,
    }


def evaluate(**overrides):
    snapshots, comparisons = window()
    values = {
        "snapshots": snapshots,
        "comparisons": comparisons,
        "contract": contract(),
        "measurements": measurements(comparisons),
        "evidence_snapshot": {
            "packet_id": "evidence:window-1",
            "source_hashes": [EVIDENCE_A, EVIDENCE_B, EVIDENCE_C],
        },
        "provenance": {
            "source_id": "camera-window:1",
            "tool_id": "completion-evaluator:v1",
            "git_commit": "abc123",
        },
    }
    values.update(overrides)
    return evaluate_completion(**values)


def test_complete_eligible_requires_every_declared_predicate_to_pass():
    result = evaluate()

    assert result["status"] == "COMPLETE_ELIGIBLE"
    assert result["evaluation_eligible"] is True
    assert all(result["checks"].values())
    assert result["failed_checks"] == []
    assert result["uncertain_checks"] == []
    assert result["observation_count"] == 3
    assert result["observed_max_distance"] == 0.05
    assert result["observed_stable_count"] == 2


@pytest.mark.parametrize(
    ("field", "value", "failed_check"),
    [
        ("observed_coverage", 0.5, "coverage"),
        ("sampling_window_valid", False, "window_valid"),
        ("unresolved_required_signals", ["signal:camera-south"], "required_signals"),
    ],
)
def test_demonstrated_predicate_failure_is_incomplete(field, value, failed_check):
    snapshots, comparisons = window()
    measured = measurements(comparisons)
    measured[field] = value

    result = evaluate(
        snapshots=snapshots,
        comparisons=comparisons,
        measurements=measured,
    )

    assert result["status"] == "INCOMPLETE"
    assert result["evaluation_eligible"] is False
    assert failed_check in result["failed_checks"]


def test_distance_failure_resets_trailing_stable_count():
    snapshots, comparisons = window()
    measured = measurements(comparisons)
    measured["comparison_distances"] = {
        comparisons[0]["comparison_id"]: 0.05,
        comparisons[1]["comparison_id"]: 0.2,
    }

    result = evaluate(
        snapshots=snapshots,
        comparisons=comparisons,
        measurements=measured,
    )

    assert result["status"] == "INCOMPLETE"
    assert result["observed_max_distance"] == 0.2
    assert result["observed_stable_count"] == 0
    assert "distance" in result["failed_checks"]
    assert "stable_count" in result["failed_checks"]


@pytest.mark.parametrize(
    ("field", "uncertain_check"),
    [
        ("provenance_check_passed", "provenance"),
        ("uncertainty_within_bounds", "uncertainty"),
    ],
)
def test_unproven_required_support_is_uncertain(field, uncertain_check):
    snapshots, comparisons = window()
    measured = measurements(comparisons)
    measured[field] = False

    result = evaluate(
        snapshots=snapshots,
        comparisons=comparisons,
        measurements=measured,
    )

    assert result["status"] == "UNCERTAIN"
    assert result["evaluation_eligible"] is False
    assert uncertain_check in result["uncertain_checks"]


def test_uncertainty_is_not_hidden_by_a_demonstrated_failure():
    snapshots, comparisons = window()
    measured = measurements(comparisons)
    measured["observed_coverage"] = 0.5
    measured["provenance_check_passed"] = False

    result = evaluate(
        snapshots=snapshots,
        comparisons=comparisons,
        measurements=measured,
    )

    assert result["status"] == "UNCERTAIN"
    assert "coverage" in result["failed_checks"]
    assert "provenance" in result["uncertain_checks"]


def test_certificate_is_non_accepting_and_has_no_write_authority():
    result = evaluate()

    assert result["type"] == CERTIFICATE_TYPE
    assert result["version"] == CERTIFICATE_VERSION
    assert result["correction_evaluated"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert "does not establish truth" in result["interpretation_notice"]


def test_certificate_is_deterministic_and_binds_ordered_inputs():
    first = evaluate()
    second = evaluate()

    assert first == second
    assert len(first["certificate_id"]) == 64
    assert len(first["observation_hashes"]) == 3
    assert len(first["comparison_hashes"]) == 2


def test_evidence_snapshot_changes_certificate_identity():
    first = evaluate()
    second = evaluate(
        evidence_snapshot={
            "packet_id": "evidence:window-2",
            "source_hashes": [EVIDENCE_A, EVIDENCE_B, EVIDENCE_C],
        }
    )

    assert first["evidence_snapshot_sha256"] != second["evidence_snapshot_sha256"]
    assert first["certificate_id"] != second["certificate_id"]


def test_tampered_snapshot_is_rejected_without_certificate():
    snapshots, comparisons = window()
    snapshots[1]["observed"]["frame"] = 999

    with pytest.raises(CompletionEvaluationError, match="is invalid"):
        evaluate_completion(
            snapshots=snapshots,
            comparisons=comparisons,
            contract=contract(),
            measurements=measurements(comparisons),
            evidence_snapshot={"packet_id": "evidence:1"},
            provenance={"source_id": "source:1"},
        )


def test_comparisons_must_exactly_match_recomputed_adjacent_pairs():
    snapshots, comparisons = window()
    tampered = deepcopy(comparisons)
    tampered[0]["observed"]["changed"]["frame"]["after"] = 999

    with pytest.raises(CompletionEvaluationError, match="exactly match"):
        evaluate_completion(
            snapshots=snapshots,
            comparisons=tampered,
            contract=contract(),
            measurements=measurements(comparisons),
            evidence_snapshot={"packet_id": "evidence:1"},
            provenance={"source_id": "source:1"},
        )


def test_distance_measurements_must_cover_exact_comparison_ids():
    snapshots, comparisons = window()
    measured = measurements(comparisons)
    measured["comparison_distances"] = {"not-a-comparison": 0.01}

    with pytest.raises(CompletionEvaluationError, match="exactly cover"):
        evaluate(
            snapshots=snapshots,
            comparisons=comparisons,
            measurements=measured,
        )


def test_snapshot_schema_must_match_declared_contract():
    declared = contract()
    declared["feature_schema_id"] = "schema:other:v1"

    with pytest.raises(CompletionEvaluationError, match="must match"):
        evaluate(contract=declared)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("epsilon", float("nan")),
        ("coverage_min", 1.1),
        ("stable_count_min", 0),
        ("observation_count_min", True),
    ],
)
def test_contract_rejects_unsafe_numeric_values(field, value):
    declared = contract()
    declared[field] = value

    with pytest.raises(CompletionEvaluationError):
        evaluate(contract=declared)


def test_contract_rejects_silently_ignored_fields():
    declared = contract()
    declared["automatic_acceptance"] = True

    with pytest.raises(CompletionEvaluationError, match="unsupported fields"):
        evaluate(contract=declared)


def test_result_does_not_alias_caller_provenance_or_evidence():
    provenance = {"source_id": "source:1", "tool_id": "tool:1"}
    evidence = {"packet_id": "evidence:1", "items": ["a", "b"]}
    result = evaluate(provenance=provenance, evidence_snapshot=evidence)

    provenance["source_id"] = "changed"
    evidence["items"].append("c")

    assert result["provenance"]["source_id"] == "source:1"
    assert result["accepted"] is False