from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.environment_completion_evaluator import evaluate_completion
from holosim.environment_episode_reopen_receipt import verify_reopen_receipt
from holosim.environment_snapshot import build_snapshot
from holosim.environment_snapshot_comparator import compare_snapshots
from holosim.langgraph_checkpoint_envelope_gate import (
    CheckpointEnvelopeGateError,
    create_checkpoint_reopen_receipt,
)


def _snapshot(
    index,
    *,
    episode_id="episode:camera-1",
):
    return build_snapshot(
        episode_id=episode_id,
        environment_id="environment:lab",
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


def _checkpoint_metadata(certificate):
    return {
        "source": "loop",
        "step": 3,
        "holo_completion_certificate": certificate,
    }


def _trigger_metadata():
    return {
        "source": "update",
        "step": 4,
        "holo_trigger_snapshot": _snapshot(
            4,
            episode_id="episode:camera-1:reopen-1",
        ),
        "holo_reopen_reasons": ["new relevant evidence"],
        "holo_reopen_provenance": {
            "source_id": "langgraph:checkpoint-4"
        },
    }


def test_gate_rejects_rehashed_undeclared_parent_envelope_field():
    certificate = _completion_certificate()
    certificate["approval"] = "GRANTED"
    certificate["certificate_id"] = stable_hash(
        {
            key: value
            for key, value in certificate.items()
            if key != "certificate_id"
        }
    )

    with pytest.raises(
        CheckpointEnvelopeGateError,
        match="unsupported fields",
    ):
        create_checkpoint_reopen_receipt(
            parent_checkpoint_metadata=_checkpoint_metadata(certificate),
            trigger_checkpoint_metadata=_trigger_metadata(),
        )


def test_gate_emits_reopen_receipt_without_mutating_parent_identity():
    certificate = _completion_certificate()
    original = deepcopy(certificate)

    receipt = create_checkpoint_reopen_receipt(
        parent_checkpoint_metadata=_checkpoint_metadata(certificate),
        trigger_checkpoint_metadata=_trigger_metadata(),
    )

    assert certificate == original
    assert receipt["parent_certificate_id"] == certificate["certificate_id"]
    assert receipt["relation"] == "reopens"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert verify_reopen_receipt(receipt)["valid"] is True