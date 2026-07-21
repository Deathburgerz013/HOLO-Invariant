from copy import deepcopy

import pytest

from holosim.environment_snapshot import build_snapshot
from holosim.environment_snapshot_comparator import (
    SnapshotComparisonError,
    compare_snapshots,
)
from holosim.environment_snapshot_comparison_identity import (
    build_environment_snapshot_comparison_check_identity,
)


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64


def snapshot(*, observed_at: str, temperature: int, evidence: str):
    return build_snapshot(
        episode_id="episode-1",
        environment_id="env-1",
        check_id=f"check-{observed_at}",
        check_purpose="observe bounded environment state",
        goal_reference="goal-1",
        observer_ids=["observer-1"],
        clock_id="clock-1",
        observed_at=observed_at,
        feature_schema_id="schema-1",
        observed={"temperature": temperature},
        missing=[],
        unknown=[],
        assumptions=[],
        falsifiers=["temperature differs"],
        evidence_sha256=[evidence],
        provenance={"source": "fixture"},
        uncertainty=[],
    )


def comparison():
    before = snapshot(
        observed_at="2026-07-21T12:00:00+00:00",
        temperature=42,
        evidence=EVIDENCE_A,
    )
    after = snapshot(
        observed_at="2026-07-21T13:00:00+00:00",
        temperature=43,
        evidence=EVIDENCE_B,
    )
    return compare_snapshots(before, after)


def test_comparison_check_identity_is_deterministic_and_shared():
    candidate = comparison()

    first = build_environment_snapshot_comparison_check_identity(candidate)
    second = build_environment_snapshot_comparison_check_identity(candidate)

    assert first == second
    assert first["type"] == "check_identity"
    assert first["check_type"] == "environment_snapshot_comparison"
    assert first["subject"]["environment_id"] == "env-1"
    assert first["subject"]["episode_id"] == "episode-1"
    assert first["subject"]["comparison_id"] == candidate["comparison_id"]
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"


def test_comparison_identity_and_check_identity_remain_distinct():
    candidate = comparison()
    identity = build_environment_snapshot_comparison_check_identity(candidate)

    assert candidate["comparison_id"] != identity["check_identity_hash"]
    assert identity["subject"]["comparison_id"] == candidate["comparison_id"]


def test_check_identity_binds_input_pair_scope_and_evidence():
    candidate = comparison()
    identity = build_environment_snapshot_comparison_check_identity(candidate)

    assert identity["reference_ids"] == [
        candidate["before_snapshot_id"],
        candidate["after_snapshot_id"],
    ]
    assert identity["scope"]["before_observed_at"] == candidate["before_observed_at"]
    assert identity["scope"]["after_observed_at"] == candidate["after_observed_at"]
    assert identity["scope"]["context"] == candidate["context"]
    assert identity["evidence_references"] == [EVIDENCE_B, EVIDENCE_A]
    assert identity["rule_references"] == []


def test_tampered_comparison_cannot_receive_shared_check_identity():
    candidate = comparison()
    candidate["observed"]["changed"]["temperature"]["after"] = 99

    with pytest.raises(SnapshotComparisonError, match="comparison identity mismatch"):
        build_environment_snapshot_comparison_check_identity(candidate)


def test_binding_does_not_mutate_comparison():
    candidate = comparison()
    before = deepcopy(candidate)

    build_environment_snapshot_comparison_check_identity(candidate)

    assert candidate == before
