from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.environment_snapshot import (
    SNAPSHOT_TYPE,
    SNAPSHOT_VERSION,
    SnapshotValidationError,
    build_snapshot,
    verify_snapshot,
)


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64


def snapshot_kwargs():
    return {
        "episode_id": "episode:camera-1",
        "environment_id": "environment:lab",
        "check_id": "check:frame-analysis:v1",
        "check_purpose": "Observe whether recorded motion changed.",
        "goal_reference": "goal:determine-next-useful-check",
        "observer_ids": ["observer:camera-north", "tool:frame-reader:v1"],
        "clock_id": "clock:camera-north:v1",
        "observed_at": "2026-07-14T23:30:00Z",
        "feature_schema_id": "schema:camera-motion:v1",
        "observed": {"motion": True, "frame": 42},
        "missing": [{"signal": "camera-south", "reason": "not sampled"}],
        "unknown": [{"field": "occluded_region"}],
        "assumptions": [{"claim": "camera clock is calibrated"}],
        "falsifiers": [{"check": "compare independent camera"}],
        "evidence_sha256": [EVIDENCE_A, EVIDENCE_B],
        "provenance": {
            "source_id": "video-loop:frame-42",
            "tool_id": "frame-reader:v1",
            "git_commit": "abc123",
        },
        "uncertainty": [{"kind": "partial_occlusion"}],
    }


def test_snapshot_is_deterministic_under_object_key_reordering():
    first_kwargs = snapshot_kwargs()
    second_kwargs = snapshot_kwargs()
    second_kwargs["observed"] = {"frame": 42, "motion": True}
    second_kwargs["provenance"] = {
        "git_commit": "abc123",
        "tool_id": "frame-reader:v1",
        "source_id": "video-loop:frame-42",
    }

    first = build_snapshot(**first_kwargs)
    second = build_snapshot(**second_kwargs)

    assert first == second
    assert len(first["snapshot_id"]) == 64


def test_snapshot_preserves_observed_missing_unknown_and_assumed_separately():
    snapshot = build_snapshot(**snapshot_kwargs())

    assert snapshot["observed"] == {"motion": True, "frame": 42}
    assert snapshot["missing"][0]["signal"] == "camera-south"
    assert snapshot["unknown"][0]["field"] == "occluded_region"
    assert snapshot["assumptions"][0]["claim"] == (
        "camera clock is calibrated"
    )
    assert snapshot["falsifiers"][0]["check"] == (
        "compare independent camera"
    )


def test_snapshot_is_non_accepting_and_read_only_by_contract():
    snapshot = build_snapshot(**snapshot_kwargs())

    assert snapshot["type"] == SNAPSHOT_TYPE
    assert snapshot["version"] == SNAPSHOT_VERSION
    assert snapshot["accepted"] is False
    assert snapshot["write_authority"] == "NONE"
    assert verify_snapshot(snapshot)["valid"] is True


def test_observation_time_is_caller_supplied_and_identity_significant():
    first_kwargs = snapshot_kwargs()
    second_kwargs = snapshot_kwargs()
    second_kwargs["observed_at"] = "2026-07-14T23:31:00Z"

    first = build_snapshot(**first_kwargs)
    second = build_snapshot(**second_kwargs)

    assert first["observed_at"] == "2026-07-14T23:30:00Z"
    assert first["snapshot_id"] != second["snapshot_id"]


@pytest.mark.parametrize(
    "observed_at",
    ["2026-07-14T23:30:00", "not-a-time", ""],
)
def test_observation_time_requires_valid_explicit_timezone(observed_at):
    kwargs = snapshot_kwargs()
    kwargs["observed_at"] = observed_at

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


@pytest.mark.parametrize(
    "evidence",
    [[], ["not-a-hash"], [EVIDENCE_A, EVIDENCE_A], ["A" * 64]],
)
def test_evidence_hashes_are_required_strict_and_unique(evidence):
    kwargs = snapshot_kwargs()
    kwargs["evidence_sha256"] = evidence

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


def test_observers_are_required_and_unique():
    kwargs = snapshot_kwargs()
    kwargs["observer_ids"] = ["observer:camera", "observer:camera"]

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


def test_snapshot_does_not_alias_mutable_caller_values():
    kwargs = snapshot_kwargs()
    observed = kwargs["observed"]
    snapshot = build_snapshot(**kwargs)

    observed["frame"] = 99

    assert snapshot["observed"]["frame"] == 42
    assert verify_snapshot(snapshot)["valid"] is True


def test_verification_detects_tampering_without_repair():
    snapshot = build_snapshot(**snapshot_kwargs())
    tampered = deepcopy(snapshot)
    tampered["observed"]["frame"] = 99

    result = verify_snapshot(tampered)

    assert result["valid"] is False
    assert "snapshot identity mismatch" in result["violations"]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert tampered["observed"]["frame"] == 99


def test_unsupported_nested_value_is_rejected():
    kwargs = snapshot_kwargs()
    kwargs["observed"] = {"unsupported": {"set"}}

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


def test_verification_rejects_invalid_fields_even_with_recomputed_hash():
    snapshot = build_snapshot(**snapshot_kwargs())
    invalid = deepcopy(snapshot)
    invalid["observed_at"] = "2026-07-14T23:30:00"
    invalid["snapshot_id"] = stable_hash(
        {
            key: value
            for key, value in invalid.items()
            if key != "snapshot_id"
        }
    )

    result = verify_snapshot(invalid)

    assert result["valid"] is False
    assert any(
        "explicit timezone" in violation
        for violation in result["violations"]
    )