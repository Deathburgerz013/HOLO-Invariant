"""Tests for configured permit-registry binding."""

import inspect

import pytest

from holosim.permitted_observation_executor import (
    PermittedObservationExecutor,
)
from holosim.permit_consumption import consume_permit


def test_executor_requires_absolute_registry_path():
    with pytest.raises(ValueError, match="absolute"):
        PermittedObservationExecutor(
            permit_registry_path="relative/permits.sqlite3"
        )


def test_observation_cannot_override_registry_path():
    parameters = inspect.signature(
        PermittedObservationExecutor.observe
    ).parameters

    assert "permit_registry_path" not in parameters


def test_two_executors_share_durable_consumption(tmp_path):
    registry = tmp_path / "permits.sqlite3"

    first = PermittedObservationExecutor(
        permit_registry_path=registry
    )
    second = PermittedObservationExecutor(
        permit_registry_path=registry
    )

    assert first._permit_registry_path == second._permit_registry_path

    assert consume_permit(
        first._permit_registry_path,
        source_id="operator",
        occurrence_id="shared-permit",
    ) is True

    assert consume_permit(
        second._permit_registry_path,
        source_id="operator",
        occurrence_id="shared-permit",
    ) is False



def test_signed_permit_replay_across_executors(tmp_path):
    from holosim.hook_contract import build_hook_request
    from holosim.observation_permit import observation_root_sha256
    from holosim.signed_occurrence import build_signed_occurrence

    secret = b"p" * 32
    observed_at = "2026-08-04T12:30:00-07:00"

    (tmp_path / "state.txt").write_bytes(b"5")

    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )

    candidate = {
        "candidate_id": "read-current-state",
        "request": request,
        "evidence_references": ["evidence:current-environment"],
        "rule_references": ["invariant:bounded-observation"],
        "comparison_status": "SUPPORTED",
        "uncertainty": "LOW",
        "unresolved_conflicts": [],
        "value": 5,
        "cost": 1,
        "urgency": 0,
        "dependency_impact": 0,
    }

    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="executor-replay",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:executor-replay",
        secret=secret,
    )

    registry = tmp_path / "permits.sqlite3"

    def observe(executor):
        return executor.observe(
            goal_reference="goal:observe-current-state",
            reference_state="state:before-observation",
            candidates=[candidate],
            allowed_root=tmp_path,
            observed_at=observed_at,
            permit_occurrence=permit,
            permit_source_secrets={"operator": secret},
            seen_occurrence_ids=set(),
            expected_content="5",
        )

    first = observe(
        PermittedObservationExecutor(
            permit_registry_path=registry
        )
    )

    second = observe(
        PermittedObservationExecutor(
            permit_registry_path=registry
        )
    )

    assert first.decision == "OBSERVED"
    assert first.classification == "SUPPORTED"
    assert first.evidence_valid is True
    assert first.permit_verified is True
    assert first.observation_performed is True

    assert second.decision == "HALT_UNPERMITTED"
    assert second.classification == "UNAVAILABLE"
    assert second.evidence_valid is False
    assert second.observation_performed is False
    assert second.request_hash is None
    assert second.result_hash is None

    for result in (first, second):
        assert result.accepted is False
        assert result.write_authority == "NONE"
        assert result.execution_authority == "NONE"



def test_consumed_permit_registry_releases_file_handles(tmp_path):
    from pathlib import Path
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(dir=tmp_path) as directory:
        root = Path(directory)
        registry = root / "permits.sqlite3"

        assert consume_permit(
            registry,
            source_id="operator",
            occurrence_id="cleanup-test",
        ) is True

        assert consume_permit(
            registry,
            source_id="operator",
            occurrence_id="cleanup-test",
        ) is False

        assert registry.exists()

    assert not root.exists()
