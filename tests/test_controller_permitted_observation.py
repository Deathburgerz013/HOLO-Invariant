
"""Tests for controller-restricted, host-owned permitted observations."""

from datetime import datetime, timezone

import pytest

from holosim.controller_permitted_observation import (
    ControllerPermittedObservation,
)
from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
    build_absence_model_receipt,
    build_causal_controller_receipt,
)
from holosim.hook_contract import build_hook_request
from holosim.observation_permit import observation_root_sha256
from holosim.permitted_observation_host import PermittedObservationHost
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"p" * 32
NOW = datetime(2026, 8, 4, 19, 30, tzinfo=timezone.utc)


def make_adapter(tmp_path, *, secret=SECRET, clock=None):
    root = tmp_path / "observation-root"
    root.mkdir(exist_ok=True)

    host = PermittedObservationHost(
        permit_registry_path=tmp_path / "permits.sqlite3",
        allowed_root=root,
        source_secrets={"operator": secret},
        clock=clock if clock is not None else lambda: NOW,
    )

    return ControllerPermittedObservation(host=host), host, root


def make_controller(
    *,
    world_available=True,
    self_available=True,
    connected=True,
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

    return absence, controller


def make_candidate():
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

    return request, candidate


def make_permit(
    root,
    request,
    *,
    secret=SECRET,
    occurrence_id="controller-gate-permit",
):
    return build_signed_occurrence(
        source_id="operator",
        occurrence_id=occurrence_id,
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(root),
            "not_before": "2026-08-04T19:00:00+00:00",
            "not_after": "2026-08-04T20:00:00+00:00",
        },
        observed_at="2026-08-04T18:59:00+00:00",
        sequence=1,
        nonce=f"nonce:{occurrence_id}",
        secret=secret,
    )


def observe(
    adapter,
    absence,
    controller,
    *,
    candidates=None,
    permit=None,
):
    return adapter.observe(
        absence_receipt=absence,
        controller_receipt=controller,
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[] if candidates is None else candidates,
        permit_occurrence=permit,
        expected_content="5",
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
def test_controller_blocks_without_invoking_host(
    monkeypatch,
    tmp_path,
    world_available,
    self_available,
    connected,
):
    adapter, host, _ = make_adapter(tmp_path)

    absence, controller = make_controller(
        world_available=world_available,
        self_available=self_available,
        connected=connected,
    )

    def forbidden_observe(*args, **kwargs):
        raise AssertionError("Blocked controller reached host")

    monkeypatch.setattr(host, "observe", forbidden_observe)

    result = observe(adapter, absence, controller)

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


def test_tampered_controller_cannot_reach_host(monkeypatch, tmp_path):
    adapter, host, _ = make_adapter(tmp_path)

    absence, controller = make_controller()
    controller["declared_action"] = "HALT"

    def forbidden_observe(*args, **kwargs):
        raise AssertionError("Invalid evidence reached host")

    monkeypatch.setattr(host, "observe", forbidden_observe)

    with pytest.raises(FunctionalConsciousnessExperimentError):
        observe(adapter, absence, controller)


def test_controller_blocks_then_permits_once_then_rejects_replay(tmp_path):
    adapter, _, root = make_adapter(tmp_path)
    (root / "state.txt").write_bytes(b"5")

    request, candidate = make_candidate()
    permit = make_permit(root, request)

    halted_absence, halted_controller = make_controller(
        world_available=False,
        self_available=False,
    )

    blocked = observe(
        adapter,
        halted_absence,
        halted_controller,
        candidates=[candidate],
        permit=permit,
    )

    assert blocked.decision == "HALT_CONTROLLER"
    assert blocked.observation_performed is False
    assert blocked.permit_verified is False
    assert blocked.evidence_valid is False
    assert blocked.request_hash is None
    assert blocked.result_hash is None

    ready_absence, ready_controller = make_controller()

    first = observe(
        adapter,
        ready_absence,
        ready_controller,
        candidates=[candidate],
        permit=permit,
    )

    assert first.decision == "OBSERVED"
    assert first.classification == "SUPPORTED"
    assert first.observation_performed is True
    assert first.permit_verified is True
    assert first.evidence_valid is True
    assert first.request_hash is not None
    assert first.result_hash is not None

    replay = observe(
        adapter,
        ready_absence,
        ready_controller,
        candidates=[candidate],
        permit=permit,
    )

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
    adapter, _, _ = make_adapter(tmp_path)

    with pytest.raises(TypeError):
        adapter.observe(
            permit_registry_path=tmp_path / "alternate.sqlite3",
        )


def test_controller_cannot_override_host_root(tmp_path):
    adapter, _, root = make_adapter(tmp_path)
    (root / "state.txt").write_text("5", encoding="utf-8")

    request, candidate = make_candidate()
    other_root = tmp_path / "untrusted-root"
    other_root.mkdir()
    (other_root / "state.txt").write_text("5", encoding="utf-8")

    permit = make_permit(
        other_root,
        request,
        occurrence_id="wrong-root",
    )
    absence, controller = make_controller()

    result = observe(
        adapter,
        absence,
        controller,
        candidates=[candidate],
        permit=permit,
    )

    assert result.decision == "HALT_UNPERMITTED"
    assert result.classification == "UNAVAILABLE"
    assert result.observation_performed is False
    assert result.permit_verified is True
    assert result.evidence_valid is False
    assert result.request_hash is None
    assert result.result_hash is None
    assert result.accepted is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"



def test_controller_cannot_override_host_signing_secret(tmp_path):
    adapter, _, root = make_adapter(tmp_path)
    (root / "state.txt").write_text("5", encoding="utf-8")

    request, candidate = make_candidate()
    forged = make_permit(
        root,
        request,
        secret=b"f" * 32,
        occurrence_id="forged-controller-permit",
    )
    absence, controller = make_controller()

    result = observe(
        adapter,
        absence,
        controller,
        candidates=[candidate],
        permit=forged,
    )

    assert result.decision == "HALT_UNPERMITTED"
    assert result.observation_performed is False
    assert result.permit_verified is False


def test_controller_cannot_override_host_clock(tmp_path):
    future = datetime(2026, 8, 5, 19, 30, tzinfo=timezone.utc)
    adapter, _, root = make_adapter(
        tmp_path,
        clock=lambda: future,
    )
    (root / "state.txt").write_text("5", encoding="utf-8")

    request, candidate = make_candidate()
    expired = make_permit(
        root,
        request,
        occurrence_id="expired-controller-permit",
    )
    absence, controller = make_controller()

    result = observe(
        adapter,
        absence,
        controller,
        candidates=[candidate],
        permit=expired,
    )

    assert result.decision == "HALT_UNPERMITTED"
    assert result.observation_performed is False
    assert result.permit_verified is True
    assert result.evidence_valid is False
    assert result.request_hash is None
    assert result.result_hash is None
