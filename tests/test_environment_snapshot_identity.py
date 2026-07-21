from copy import deepcopy

import pytest

from holosim.environment_snapshot import SnapshotValidationError, build_snapshot
from holosim.environment_snapshot_identity import (
    build_environment_snapshot_check_identity,
)


EVIDENCE = "a" * 64


def snapshot():
    return build_snapshot(
        episode_id="episode-1",
        environment_id="env-1",
        check_id="check-1",
        check_purpose="observe bounded environment state",
        goal_reference="goal-1",
        observer_ids=["observer-1"],
        clock_id="clock-1",
        observed_at="2026-07-21T12:00:00+00:00",
        feature_schema_id="schema-1",
        observed={"temperature": 42},
        missing=[],
        unknown=["future-state"],
        assumptions=[],
        falsifiers=["temperature differs"],
        evidence_sha256=[EVIDENCE],
        provenance={"source": "fixture"},
        uncertainty=[],
    )


def test_snapshot_check_identity_is_deterministic_and_shared():
    candidate = snapshot()

    first = build_environment_snapshot_check_identity(candidate)
    second = build_environment_snapshot_check_identity(candidate)

    assert first == second
    assert first["type"] == "check_identity"
    assert first["check_id"] == "check-1"
    assert first["check_type"] == "environment_observation"
    assert first["subject"]["environment_id"] == "env-1"
    assert first["subject"]["episode_id"] == "episode-1"
    assert first["subject"]["snapshot_id"] == candidate["snapshot_id"]
    assert first["input_state_hash"] == candidate["snapshot_id"]
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"


def test_snapshot_identity_and_check_identity_remain_distinct():
    candidate = snapshot()
    identity = build_environment_snapshot_check_identity(candidate)

    assert candidate["snapshot_id"] != identity["check_identity_hash"]
    assert identity["subject"]["snapshot_id"] == candidate["snapshot_id"]


def test_check_identity_binds_reference_scope_evidence_and_rules():
    identity = build_environment_snapshot_check_identity(snapshot())

    assert identity["reference_ids"] == ["goal-1", "schema-1"]
    assert identity["scope"] == {
        "check_purpose": "observe bounded environment state",
        "observer_ids": ["observer-1"],
        "clock_id": "clock-1",
        "observed_at": "2026-07-21T12:00:00+00:00",
    }
    assert identity["evidence_references"] == [EVIDENCE]
    assert identity["rule_references"] == ["schema-1"]


def test_invalid_snapshot_cannot_receive_shared_check_identity():
    candidate = snapshot()
    candidate["observed"]["temperature"] = 99

    with pytest.raises(SnapshotValidationError, match="invalid snapshot"):
        build_environment_snapshot_check_identity(candidate)


def test_binding_does_not_mutate_snapshot():
    candidate = snapshot()
    before = deepcopy(candidate)

    build_environment_snapshot_check_identity(candidate)

    assert candidate == before
