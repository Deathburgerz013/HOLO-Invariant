
"""Tests for controller-restricted permitted observations."""

import pytest

from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
    build_absence_model_receipt,
    build_causal_controller_receipt,
)
from holosim.controller_permitted_observation import (
    ControllerPermittedObservation,
)


@pytest.mark.parametrize(
    ("world_available", "self_available", "connected"),
    [
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (False, False, True),
    ],
)
def test_controller_blocks_without_invoking_executor(
    monkeypatch,
    tmp_path,
    world_available,
    self_available,
    connected,
):
    absence = build_absence_model_receipt(
        experiment_id="experiment:controller-gate",
        condition_id="condition:bounded-observation",
        world_source_id="source:world",
        self_source_id="source:self",
        world_channel_available=world_available,
        self_channel_available=self_available,
    )

    controller = build_causal_controller_receipt(
        experiment_id="experiment:controller-gate",
        condition_id="condition:bounded-observation",
        absence_receipt=absence,
        controller_connected=connected,
    )

    def forbidden_observe(*args, **kwargs):
        raise AssertionError("Blocked controller reached executor")

    monkeypatch.setattr(
        "holosim.controller_permitted_observation."
        "PermittedObservationExecutor.observe",
        forbidden_observe,
    )

    adapter = ControllerPermittedObservation(
        permit_registry_path=tmp_path / "permits.sqlite3",
    )

    result = adapter.observe(
        absence_receipt=absence,
        controller_receipt=controller,
        goal_reference="goal:observation",
        reference_state="state:before",
        candidates=[],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=None,
        permit_source_secrets={},
        seen_occurrence_ids=set(),
        expected_content="5",
    )

    assert result.decision == "HALT_CONTROLLER"
    assert result.classification == "UNAVAILABLE"
    assert result.evidence_valid is False
    assert result.permit_verified is False
    assert result.observation_performed is False
    assert result.request_hash is None
    assert result.result_hash is None
    assert result.accepted is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"


def test_tampered_controller_cannot_reach_executor(monkeypatch, tmp_path):
    absence = build_absence_model_receipt(
        experiment_id="experiment:controller-gate",
        condition_id="condition:bounded-observation",
        world_source_id="source:world",
        self_source_id="source:self",
        world_channel_available=True,
        self_channel_available=True,
    )

    controller = build_causal_controller_receipt(
        experiment_id="experiment:controller-gate",
        condition_id="condition:bounded-observation",
        absence_receipt=absence,
        controller_connected=True,
    )

    controller["declared_action"] = "HALT"

    def forbidden_observe(*args, **kwargs):
        raise AssertionError("Invalid evidence reached executor")

    monkeypatch.setattr(
        "holosim.controller_permitted_observation."
        "PermittedObservationExecutor.observe",
        forbidden_observe,
    )

    adapter = ControllerPermittedObservation(
        permit_registry_path=tmp_path / "permits.sqlite3",
    )

    with pytest.raises(FunctionalConsciousnessExperimentError):
        adapter.observe(
            absence_receipt=absence,
            controller_receipt=controller,
            goal_reference="goal:observation",
            reference_state="state:before",
            candidates=[],
            allowed_root=tmp_path,
            observed_at="2026-08-04T12:30:00-07:00",
            permit_occurrence=None,
            permit_source_secrets={},
            seen_occurrence_ids=set(),
            expected_content="5",
        )


def test_controller_blocks_then_permits_once_then_rejects_replay(tmp_path):
    from holosim.hook_contract import build_hook_request
    from holosim.observation_permit import observation_root_sha256
    from holosim.signed_occurrence import build_signed_occurrence

    secret = b"p" * 32
    observed_at = "2026-08-04T12:30:00-07:00"
    registry = tmp_path / "permits.sqlite3"

    adapter = ControllerPermittedObservation(
        permit_registry_path=registry,
    )

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
        occurrence_id="controller-gate-permit",
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
        nonce="nonce:controller-gate-permit",
        secret=secret,
    )

    def controller_for(*, world_available, self_available):
        absence = build_absence_model_receipt(
            experiment_id="experiment:controller-gate",
            condition_id="condition:bounded-observation",
            world_source_id="source:world",
            self_source_id="source:self",
            world_channel_available=world_available,
            self_channel_available=self_available,
        )

        controller = build_causal_controller_receipt(
            experiment_id="experiment:controller-gate",
            condition_id="condition:bounded-observation",
            absence_receipt=absence,
            controller_connected=True,
        )

        return absence, controller

    def observe(absence, controller):
        return adapter.observe(
            absence_receipt=absence,
            controller_receipt=controller,
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

    # Both channels unavailable: controller blocks observation.
    halted_absence, halted_controller = controller_for(
        world_available=False,
        self_available=False,
    )

    blocked = observe(halted_absence, halted_controller)

    assert blocked.decision == "HALT_CONTROLLER"
    assert blocked.observation_performed is False
    assert blocked.permit_verified is False
    assert blocked.evidence_valid is False
    assert blocked.request_hash is None
    assert blocked.result_hash is None

    # Both channels reported available: the independent permit is required.
    ready_absence, ready_controller = controller_for(
        world_available=True,
        self_available=True,
    )

    first = observe(ready_absence, ready_controller)

    assert first.decision == "OBSERVED"
    assert first.classification == "SUPPORTED"
    assert first.observation_performed is True
    assert first.permit_verified is True
    assert first.evidence_valid is True
    assert first.request_hash is not None
    assert first.result_hash is not None

    # The consumed signed permit cannot authorize another observation.
    replay = observe(ready_absence, ready_controller)

    assert replay.decision == "HALT_UNPERMITTED"
    assert replay.classification == "UNAVAILABLE"
    assert replay.observation_performed is False
    assert replay.evidence_valid is False
    assert replay.request_hash is None
    assert replay.result_hash is None

    for result in (blocked, first, replay):
        assert result.accepted is False
        assert result.write_authority == "NONE"
        assert result.execution_authority == "NONE"


def test_registry_cannot_be_overridden_per_observation(tmp_path):
    adapter = ControllerPermittedObservation(
        permit_registry_path=tmp_path / "trusted.sqlite3",
    )

    with pytest.raises(TypeError):
        adapter.observe(
            permit_registry_path=tmp_path / "alternate.sqlite3",
        )
