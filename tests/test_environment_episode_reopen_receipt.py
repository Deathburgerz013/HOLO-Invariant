from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.environment_completion_evaluator import evaluate_completion
from holosim.environment_episode_reopen_receipt import (
    EpisodeReopenError,
    REOPEN_RECEIPT_TYPE,
    REOPEN_RECEIPT_VERSION,
    create_reopen_receipt,
    verify_reopen_receipt,
)
from holosim.environment_snapshot import build_snapshot
from holosim.environment_snapshot_comparator import compare_snapshots


def _snapshot(
    index,
    *,
    episode_id="episode:camera-1",
    environment_id="environment:lab",
):
    return build_snapshot(
        episode_id=episode_id,
        environment_id=environment_id,
        check_id="check:stability:v1",
        check_purpose="Observe bounded environmental change.",
        goal_reference="goal:evaluate-completion-eligibility",
        observer_ids=["observer:camera-north"],
        clock_id="clock:camera-north:v1",
        observed_at=f"2026-07-14T23:3{index}:00Z",
        feature_schema_id="schema:camera-motion:v1",
        observed={"motion_score": index / 100},
        missing=[],
        unknown=[],
        assumptions=[{"claim": "camera clock is calibrated"}],
        falsifiers=[{"check": "compare independent camera"}],
        evidence_sha256=[f"{index + 1:x}" * 64],
        provenance={"source_id": f"camera:frame-{index}"},
        uncertainty=[],
    )


def _completion_certificate():
    snapshots = [_snapshot(index) for index in range(3)]
    comparisons = [
        compare_snapshots(before, after)
        for before, after in zip(snapshots, snapshots[1:])
    ]
    return evaluate_completion(
        snapshots=snapshots,
        comparisons=comparisons,
        contract={
            "feature_schema_id": "schema:camera-motion:v1",
            "distance_metric_id": "metric:normalized-motion:v1",
            "epsilon": 0.1,
            "coverage_measure_id": "coverage:required-surfaces:v1",
            "coverage_min": 0.9,
            "stable_count_min": 2,
            "observation_count_min": 3,
            "sampling_policy_id": "sampling:one-minute:v1",
            "required_signal_schema_id": "signals:camera-motion:v1",
        },
        measurements={
            "comparison_distances": {
                comparison["comparison_id"]: 0.05
                for comparison in comparisons
            },
            "observed_coverage": 1.0,
            "unresolved_required_signals": [],
            "sampling_window_valid": True,
            "provenance_check_passed": True,
            "uncertainty_within_bounds": True,
        },
        evidence_snapshot={"packet_id": "evidence:window-1"},
        provenance={"source_id": "camera-window:1"},
    )


def test_later_relevant_observation_reopens_completed_episode_without_mutation():
    certificate = _completion_certificate()
    trigger_snapshot = _snapshot(
        4,
        episode_id="episode:camera-1:reopen-1",
    )

    receipt = create_reopen_receipt(
        completion_certificate=certificate,
        trigger_snapshot=trigger_snapshot,
        relation="reopens",
        reasons=["new relevant evidence"],
        provenance={"source_id": "operator-review:1"},
    )

    assert receipt["type"] == REOPEN_RECEIPT_TYPE
    assert receipt["version"] == REOPEN_RECEIPT_VERSION
    assert receipt["relation"] == "reopens"
    assert receipt["parent_certificate_id"] == certificate["certificate_id"]
    assert receipt["prior_episode_id"] == certificate["episode_id"]
    assert receipt["reopened_episode_id"] == trigger_snapshot["episode_id"]
    assert receipt["trigger_snapshot_id"] == trigger_snapshot["snapshot_id"]
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert certificate["status"] == "COMPLETE_ELIGIBLE"
    assert verify_reopen_receipt(receipt)["valid"] is True


def _valid_receipt():
    return create_reopen_receipt(
        completion_certificate=_completion_certificate(),
        trigger_snapshot=_snapshot(
            4,
            episode_id="episode:camera-1:reopen-1",
        ),
        relation="reopens",
        reasons=["new relevant evidence"],
        provenance={"source_id": "operator-review:1"},
    )


def test_reopen_requires_a_distinct_episode_identity():
    with pytest.raises(EpisodeReopenError, match="distinct episode_id"):
        create_reopen_receipt(
            completion_certificate=_completion_certificate(),
            trigger_snapshot=_snapshot(4),
            relation="reopens",
            reasons=["new relevant evidence"],
            provenance={"source_id": "operator-review:1"},
        )


def test_reopen_requires_the_same_environment():
    with pytest.raises(EpisodeReopenError, match="same environment"):
        create_reopen_receipt(
            completion_certificate=_completion_certificate(),
            trigger_snapshot=_snapshot(
                4,
                episode_id="episode:camera-1:reopen-1",
                environment_id="environment:other",
            ),
            relation="reopens",
            reasons=["new relevant evidence"],
            provenance={"source_id": "operator-review:1"},
        )


def test_reopen_trigger_must_be_later_than_completed_window():
    with pytest.raises(EpisodeReopenError, match="must be later"):
        create_reopen_receipt(
            completion_certificate=_completion_certificate(),
            trigger_snapshot=_snapshot(
                2,
                episode_id="episode:camera-1:reopen-1",
            ),
            relation="reopens",
            reasons=["new relevant evidence"],
            provenance={"source_id": "operator-review:1"},
        )


def test_tampered_completion_certificate_cannot_open_a_branch():
    certificate = _completion_certificate()
    certificate["accepted"] = True

    with pytest.raises(EpisodeReopenError, match="non-accepting"):
        create_reopen_receipt(
            completion_certificate=certificate,
            trigger_snapshot=_snapshot(
                4,
                episode_id="episode:camera-1:reopen-1",
            ),
            relation="reopens",
            reasons=["new relevant evidence"],
            provenance={"source_id": "operator-review:1"},
        )


def test_tampered_trigger_snapshot_cannot_open_a_branch():
    snapshot = _snapshot(
        4,
        episode_id="episode:camera-1:reopen-1",
    )
    snapshot["observed"]["motion_score"] = 999

    with pytest.raises(EpisodeReopenError, match="trigger snapshot is invalid"):
        create_reopen_receipt(
            completion_certificate=_completion_certificate(),
            trigger_snapshot=snapshot,
            relation="reopens",
            reasons=["new relevant evidence"],
            provenance={"source_id": "operator-review:1"},
        )


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("accepted", True),
        ("write_authority", "GRANTED"),
        ("relation", "supersedes"),
        ("parent_certificate_id", "f" * 64),
        ("trigger_snapshot_id", "e" * 64),
    ],
)
def test_verifier_rejects_rehashed_forged_boundary_or_lineage(
    field,
    forged_value,
):
    receipt = deepcopy(_valid_receipt())
    receipt[field] = forged_value
    receipt["receipt_id"] = stable_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_id"
        }
    )

    result = verify_reopen_receipt(receipt)

    assert result["valid"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_verifier_rejects_rehashed_undeclared_fields():
    receipt = deepcopy(_valid_receipt())
    receipt["approval"] = "GRANTED"
    receipt["receipt_id"] = stable_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_id"
        }
    )

    result = verify_reopen_receipt(receipt)

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]


def test_reopen_rejects_rehashed_undeclared_completion_certificate_field():
    certificate = _completion_certificate()
    certificate["approval"] = "GRANTED"
    certificate["certificate_id"] = stable_hash(
        {
            key: value
            for key, value in certificate.items()
            if key != "certificate_id"
        }
    )

    with pytest.raises(EpisodeReopenError, match="unsupported fields"):
        create_reopen_receipt(
            completion_certificate=certificate,
            trigger_snapshot=_snapshot(
                4,
                episode_id="episode:camera-1:reopen-1",
            ),
            relation="reopens",
            reasons=["new relevant evidence"],
            provenance={"source_id": "operator-review:1"},
        )
