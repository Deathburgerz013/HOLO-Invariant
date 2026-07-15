from copy import deepcopy

import pytest

from holosim.environment_snapshot import build_snapshot
from holosim.environment_snapshot_comparator import (
    COMPARISON_TYPE,
    COMPARISON_VERSION,
    SnapshotComparisonError,
    compare_snapshots,
)


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64
EVIDENCE_C = "c" * 64


def snapshot_kwargs(observed_at="2026-07-14T23:30:00Z"):
    return {
        "episode_id": "episode:camera-1",
        "environment_id": "environment:lab",
        "check_id": "check:frame-analysis:v1",
        "check_purpose": "Observe whether recorded motion changed.",
        "goal_reference": "goal:determine-next-useful-check",
        "observer_ids": ["observer:camera-north", "tool:frame-reader:v1"],
        "clock_id": "clock:camera-north:v1",
        "observed_at": observed_at,
        "feature_schema_id": "schema:camera-motion:v1",
        "observed": {"motion": False, "frame": 41, "temperature": 20},
        "missing": [{"signal": "camera-south", "reason": "not sampled"}],
        "unknown": [{"field": "occluded_region"}],
        "assumptions": [{"claim": "camera clock is calibrated"}],
        "falsifiers": [{"check": "compare independent camera"}],
        "evidence_sha256": [EVIDENCE_A, EVIDENCE_B],
        "provenance": {
            "source_id": "video-loop:frame-41",
            "tool_id": "frame-reader:v1",
            "git_commit": "abc123",
        },
        "uncertainty": [{"kind": "partial_occlusion"}],
    }


def snapshot_pair():
    before = build_snapshot(**snapshot_kwargs())
    after_kwargs = snapshot_kwargs("2026-07-14T23:31:00Z")
    after_kwargs["observed"] = {
        "motion": True,
        "frame": 42,
        "humidity": 50,
    }
    after_kwargs["missing"] = []
    after_kwargs["unknown"] = [
        {"field": "occluded_region"},
        {"field": "audio_source"},
    ]
    after_kwargs["assumptions"] = [
        {"claim": "camera clock is calibrated"},
        {"claim": "lighting remained constant"},
    ]
    after_kwargs["falsifiers"] = [{"check": "inspect raw timestamps"}]
    after_kwargs["evidence_sha256"] = [EVIDENCE_B, EVIDENCE_C]
    after_kwargs["provenance"] = {
        "source_id": "video-loop:frame-42",
        "tool_id": "frame-reader:v1",
        "capture_id": "capture:42",
    }
    after_kwargs["uncertainty"] = [{"kind": "lighting_change"}]
    after = build_snapshot(**after_kwargs)
    return before, after


def test_comparison_reports_observed_add_remove_change_and_unchanged():
    before, after = snapshot_pair()

    result = compare_snapshots(before, after)

    assert result["observed"]["added"] == {"humidity": 50}
    assert result["observed"]["removed"] == {"temperature": 20}
    assert result["observed"]["changed"] == {
        "frame": {"before": 41, "after": 42},
        "motion": {"before": False, "after": True},
    }
    assert result["observed"]["unchanged_keys"] == []


def test_comparison_keeps_epistemic_categories_separate():
    before, after = snapshot_pair()

    result = compare_snapshots(before, after)

    assert result["missing"]["removed"] == before["missing"]
    assert result["unknown"]["retained"] == before["unknown"]
    assert result["unknown"]["added"] == [{"field": "audio_source"}]
    assert result["assumptions"]["added"] == [
        {"claim": "lighting remained constant"}
    ]
    assert result["falsifiers"]["removed"] == before["falsifiers"]
    assert result["uncertainty"]["added"] == [
        {"kind": "lighting_change"}
    ]


def test_comparison_reports_evidence_and_provenance_changes():
    before, after = snapshot_pair()

    result = compare_snapshots(before, after)

    assert result["evidence_sha256"] == {
        "added": [EVIDENCE_C],
        "removed": [EVIDENCE_A],
        "retained": [EVIDENCE_B],
    }
    assert result["provenance"]["added"] == {"capture_id": "capture:42"}
    assert result["provenance"]["removed"] == {"git_commit": "abc123"}
    assert result["provenance"]["changed"]["source_id"] == {
        "before": "video-loop:frame-41",
        "after": "video-loop:frame-42",
    }
    assert result["provenance"]["unchanged_keys"] == ["tool_id"]


def test_comparison_is_deterministic_and_identity_binds_both_snapshots():
    before, after = snapshot_pair()

    first = compare_snapshots(before, after)
    second = compare_snapshots(deepcopy(before), deepcopy(after))

    assert first == second
    assert len(first["comparison_id"]) == 64
    assert first["before_snapshot_id"] == before["snapshot_id"]
    assert first["after_snapshot_id"] == after["snapshot_id"]


def test_comparison_has_no_acceptance_completion_or_write_authority():
    before, after = snapshot_pair()

    result = compare_snapshots(before, after)

    assert result["type"] == COMPARISON_TYPE
    assert result["version"] == COMPARISON_VERSION
    assert result["completion_evaluated"] is False
    assert result["correction_evaluated"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert "does not establish truth" in result["interpretation_notice"]


@pytest.mark.parametrize("label", ["before", "after"])
def test_comparison_rejects_tampered_snapshots(label):
    before, after = snapshot_pair()
    target = before if label == "before" else after
    target["observed"]["frame"] = 999

    with pytest.raises(SnapshotComparisonError, match=f"{label}_snapshot is invalid"):
        compare_snapshots(before, after)


def test_comparison_requires_same_environment():
    before, _ = snapshot_pair()
    kwargs = snapshot_kwargs("2026-07-14T23:31:00Z")
    kwargs["environment_id"] = "environment:other-lab"
    after = build_snapshot(**kwargs)

    with pytest.raises(SnapshotComparisonError, match="same environment_id"):
        compare_snapshots(before, after)


def test_comparison_requires_same_episode():
    before, _ = snapshot_pair()
    kwargs = snapshot_kwargs("2026-07-14T23:31:00Z")
    kwargs["episode_id"] = "episode:camera-2"
    after = build_snapshot(**kwargs)

    with pytest.raises(SnapshotComparisonError, match="same episode_id"):
        compare_snapshots(before, after)


@pytest.mark.parametrize(
    "after_time",
    ["2026-07-14T23:30:00Z", "2026-07-14T23:29:59Z"],
)
def test_comparison_requires_strictly_later_after_snapshot(after_time):
    before = build_snapshot(**snapshot_kwargs())
    after = build_snapshot(**snapshot_kwargs(after_time))

    with pytest.raises(SnapshotComparisonError, match="must be later"):
        compare_snapshots(before, after)


def test_schema_change_is_reported_without_claiming_comparability():
    before, _ = snapshot_pair()
    kwargs = snapshot_kwargs("2026-07-14T23:31:00Z")
    kwargs["feature_schema_id"] = "schema:camera-motion:v2"
    after = build_snapshot(**kwargs)

    result = compare_snapshots(before, after)

    assert result["context"]["comparable_feature_schema"] is False
    assert result["context"]["changed"]["feature_schema_id"] == {
        "before": "schema:camera-motion:v1",
        "after": "schema:camera-motion:v2",
    }


def test_context_and_observer_changes_are_explicit():
    before, _ = snapshot_pair()
    kwargs = snapshot_kwargs("2026-07-14T23:31:00Z")
    kwargs["check_id"] = "check:frame-analysis:v2"
    kwargs["observer_ids"] = ["observer:camera-north", "tool:frame-reader:v2"]
    after = build_snapshot(**kwargs)

    result = compare_snapshots(before, after)

    assert result["context"]["changed"]["check_id"] == {
        "before": "check:frame-analysis:v1",
        "after": "check:frame-analysis:v2",
    }
    assert result["context"]["observer_ids"] == {
        "added": ["tool:frame-reader:v2"],
        "removed": ["tool:frame-reader:v1"],
        "retained": ["observer:camera-north"],
    }


def test_list_delta_preserves_duplicate_occurrence_counts():
    repeated = {"field": "repeated"}
    before_kwargs = snapshot_kwargs()
    before_kwargs["unknown"] = [repeated, repeated]
    after_kwargs = snapshot_kwargs("2026-07-14T23:31:00Z")
    after_kwargs["unknown"] = [repeated]
    before = build_snapshot(**before_kwargs)
    after = build_snapshot(**after_kwargs)

    result = compare_snapshots(before, after)

    assert result["unknown"]["retained"] == [repeated]
    assert result["unknown"]["removed"] == [repeated]
    assert result["unknown"]["added"] == []


def test_comparison_does_not_alias_snapshot_values():
    before, after = snapshot_pair()
    result = compare_snapshots(before, after)

    after["observed"]["humidity"] = 99
    before["missing"].clear()

    assert result["observed"]["added"] == {"humidity": 50}
    assert result["missing"]["removed"] == [
        {"signal": "camera-south", "reason": "not sampled"}
    ]