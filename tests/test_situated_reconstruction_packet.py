from copy import deepcopy

import pytest

from holosim.environment_invariant_receipts import (
    evaluate_environment_invariant,
    environment_fingerprint,
)
from holosim.guarantee_environment_binding import (
    bind_guarantee_environment,
)
from holosim.guarantee_registry import build_guarantee_registry
from holosim.invariant_validity_lifecycle import (
    append_validity_event,
    project_active_invariants,
)
from holosim.situated_reconstruction_packet import (
    SituatedReconstructionPacketError,
    build_situated_reconstruction_packet,
    consume_situated_reconstruction_packet,
    verify_situated_reconstruction_packet,
)


ENVIRONMENT = {
    "implementation": "CPython",
    "platform": "win32",
    "python": "3.13.7",
}
ENVIRONMENT_FINGERPRINT = environment_fingerprint(ENVIRONMENT)


def _event(history, *, claim_id, status, environment=None):
    event = append_validity_event(
        history=history,
        claim_id=claim_id,
        status=status,
        reason="bounded evidence supports this lifecycle state",
        evidence=[f"evidence:{claim_id}"],
        observed_at="2026-08-19T23:00:00Z",
        environment_fingerprint=environment,
    )
    history.append(event)
    return event


def _binding(claim_id):
    source = f"tests/{claim_id}.py"
    guarantee = {
        "guarantee_id": claim_id,
        "guarantee_type": "continuity",
        "scope": f"holosim.{claim_id}",
        "dependencies": ["declared environment"],
        "validator": f"check-{claim_id}",
        "failure_condition": "declared behavior does not hold",
        "evidence": [source],
    }
    receipt = evaluate_environment_invariant(
        invariant_id=claim_id,
        statement="The declared behavior holds in the observed environment.",
        scope={
            "target": f"holosim.{claim_id}",
            "conditions": ["declared local environment"],
        },
        environment=ENVIRONMENT,
        environment_probe=lambda: ENVIRONMENT,
        check_id=f"check-{claim_id}",
        check=lambda: True,
        observed_at="2026-08-19T23:00:00Z",
        evidence={"sources": [source]},
    )
    return bind_guarantee_environment(
        registry=build_guarantee_registry([guarantee]),
        receipt=receipt,
    )


def _inputs():
    history = []
    stable = _event(
        history,
        claim_id="cross-model-reconstruction",
        status="ESTABLISHED",
    )
    contingent = _event(
        history,
        claim_id="current-runtime-behavior",
        status="CONTINGENT",
        environment=ENVIRONMENT_FINGERPRINT,
    )
    unknown = _event(
        history,
        claim_id="unverified-context",
        status="UNKNOWN",
    )
    projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
    )
    bindings = [
        _binding("cross-model-reconstruction"),
        _binding("current-runtime-behavior"),
    ]
    return projection, bindings, stable, contingent, unknown


def _packet():
    projection, bindings, _, _, _ = _inputs()
    return build_situated_reconstruction_packet(
        projection=projection,
        bindings=bindings,
        objective="Resume bounded continuity work without transcript replay.",
        unresolved=["Determine whether unverified context still applies."],
        required_checks=["Recheck excluded claims before using them."],
    )


def test_packet_contains_only_active_environment_bound_claims():
    projection, bindings, stable, contingent, unknown = _inputs()

    packet = build_situated_reconstruction_packet(
        projection=projection,
        bindings=bindings,
        objective="Resume bounded continuity work without transcript replay.",
        unresolved=["Determine whether unverified context still applies."],
        required_checks=["Recheck excluded claims before using them."],
    )

    assert packet["type"] == "holo_situated_reconstruction_packet"
    assert packet["version"] == 1
    assert packet["environment_fingerprint"] == ENVIRONMENT_FINGERPRINT
    assert packet["projection_hash"] == projection["projection_hash"]
    assert packet["active_claims"] == [
        {
            "claim_id": "cross-model-reconstruction",
            "status": "ESTABLISHED",
            "event_hash": stable["event_hash"],
            "binding_hash": bindings[0]["binding_hash"],
        },
        {
            "claim_id": "current-runtime-behavior",
            "status": "CONTINGENT",
            "event_hash": contingent["event_hash"],
            "binding_hash": bindings[1]["binding_hash"],
        },
    ]
    assert packet["excluded_claims"] == [
        {
            "claim_id": "unverified-context",
            "status": "UNKNOWN",
            "event_hash": unknown["event_hash"],
            "exclusion_reason": "UNKNOWN",
        }
    ]


def test_packet_requires_one_held_binding_per_active_claim():
    projection, bindings, _, _, _ = _inputs()

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="missing binding for active claim",
    ):
        build_situated_reconstruction_packet(
            projection=projection,
            bindings=bindings[:1],
            objective="Resume work.",
            unresolved=["One claim remains excluded."],
            required_checks=["Recheck excluded claim."],
        )


def test_packet_rejects_binding_from_another_environment():
    projection, bindings, _, _, _ = _inputs()
    mismatched = deepcopy(bindings)
    mismatched[0]["environment_fingerprint"] = "different-environment"

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="binding is invalid",
    ):
        build_situated_reconstruction_packet(
            projection=projection,
            bindings=mismatched,
            objective="Resume work.",
            unresolved=["One claim remains excluded."],
            required_checks=["Recheck excluded claim."],
        )


def test_packet_rejects_nonheld_binding():
    projection, bindings, _, _, _ = _inputs()
    failed = deepcopy(bindings)
    failed[0]["status"] = "FAILED"

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="binding is invalid",
    ):
        build_situated_reconstruction_packet(
            projection=projection,
            bindings=failed,
            objective="Resume work.",
            unresolved=["One claim remains excluded."],
            required_checks=["Recheck excluded claim."],
        )


def test_packet_is_deterministic_and_model_independent():
    first = _packet()
    second = _packet()

    assert first == second
    assert "model" not in first
    assert "provider" not in first
    assert "transcript" not in first
    assert first["packet_hash"] == second["packet_hash"]


def test_packet_is_bounded_and_cannot_grant_authority():
    packet = _packet()

    assert packet["accepted"] is False
    assert packet["truth_claimed"] is False
    assert packet["write_authority"] == "NONE"
    assert packet["execution_authority"] == "NONE"
    assert packet["canonical_mutation"] is False
    assert verify_situated_reconstruction_packet(packet) is True


def test_tampered_packet_is_rejected():
    packet = _packet()
    tampered = deepcopy(packet)
    tampered["active_claims"][0]["status"] = "INVARIANT"

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="packet hash mismatch",
    ):
        verify_situated_reconstruction_packet(tampered)


def test_consumer_emits_minimal_resume_frame():
    packet = _packet()

    frame = consume_situated_reconstruction_packet(packet)

    assert frame == {
        "status": "SITUATED_RECONSTRUCTION_READY",
        "packet_hash": packet["packet_hash"],
        "environment_fingerprint": ENVIRONMENT_FINGERPRINT,
        "objective": "Resume bounded continuity work without transcript replay.",
        "active_claims": packet["active_claims"],
        "excluded_claims": packet["excluded_claims"],
        "unresolved": ["Determine whether unverified context still applies."],
        "required_checks": ["Recheck excluded claims before using them."],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }