from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.invariant_validity_lifecycle import project_active_invariants
from holosim.situated_reconstruction_packet import (
    SituatedReconstructionPacketError,
    build_situated_reconstruction_packet,
    consume_verified_situated_reconstruction_packet,
)
from tests.test_situated_reconstruction_packet import (
    ENVIRONMENT_FINGERPRINT,
    _binding,
    _event,
)


def _case():
    history = []

    _event(
        history,
        claim_id="cross-model-reconstruction",
        status="ESTABLISHED",
    )
    _event(
        history,
        claim_id="current-runtime-behavior",
        status="CONTINGENT",
        environment=ENVIRONMENT_FINGERPRINT,
    )
    _event(
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

    packet = build_situated_reconstruction_packet(
        projection=projection,
        bindings=bindings,
        objective="Resume bounded continuity work without transcript replay.",
        unresolved=["Determine whether unverified context still applies."],
        required_checks=["Recheck excluded claims before using them."],
    )

    return packet, history, bindings


def _rehash(packet):
    packet["packet_hash"] = stable_hash({
        key: value
        for key, value in packet.items()
        if key != "packet_hash"
    })


def test_verified_consumer_accepts_matching_sources():
    packet, history, bindings = _case()

    frame = consume_verified_situated_reconstruction_packet(
        packet,
        history=history,
        bindings=bindings,
        current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
    )

    assert frame["status"] == "SITUATED_RECONSTRUCTION_READY"
    assert frame["accepted"] is False
    assert frame["truth_claimed"] is False
    assert frame["write_authority"] == "NONE"
    assert frame["execution_authority"] == "NONE"


def test_verified_consumer_rejects_fabricated_binding_reference():
    packet, history, bindings = _case()

    fabricated = deepcopy(packet)
    fabricated["active_claims"][0]["binding_hash"] = "e" * 64
    _rehash(fabricated)

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="provenance",
    ):
        consume_verified_situated_reconstruction_packet(
            fabricated,
            history=history,
            bindings=bindings,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )


def test_verified_consumer_rejects_fabricated_event_reference():
    packet, history, bindings = _case()

    fabricated = deepcopy(packet)
    fabricated["active_claims"][0]["event_hash"] = "f" * 64
    _rehash(fabricated)

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="provenance",
    ):
        consume_verified_situated_reconstruction_packet(
            fabricated,
            history=history,
            bindings=bindings,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )


def test_verified_consumer_rejects_missing_history():
    packet, _, bindings = _case()

    with pytest.raises(SituatedReconstructionPacketError):
        consume_verified_situated_reconstruction_packet(
            packet,
            history=[],
            bindings=bindings,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )


def test_verified_consumer_rejects_missing_binding():
    packet, history, bindings = _case()

    with pytest.raises(SituatedReconstructionPacketError):
        consume_verified_situated_reconstruction_packet(
            packet,
            history=history,
            bindings=bindings[:1],
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )


def test_verified_consumer_rejects_invalid_history_event():
    packet, history, bindings = _case()

    invalid_history = deepcopy(history)
    invalid_history[0]["status"] = "INVALID"

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="invalid validity history",
    ):
        consume_verified_situated_reconstruction_packet(
            packet,
            history=invalid_history,
            bindings=bindings,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )


def test_verified_consumer_rejects_stale_environment():
    packet, history, bindings = _case()

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="current environment fingerprint mismatch",
    ):
        consume_verified_situated_reconstruction_packet(
            packet,
            history=history,
            bindings=bindings,
            current_environment_fingerprint="different-environment",
        )


@pytest.mark.parametrize("field", ["history", "bindings"])
def test_verified_consumer_rejects_oversized_sources(field):
    packet, history, bindings = _case()
    inputs = {
        "history": history,
        "bindings": bindings,
        "current_environment_fingerprint": ENVIRONMENT_FINGERPRINT,
    }
    inputs[field] = [{}] * 1001

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="exceeds maximum",
    ):
        consume_verified_situated_reconstruction_packet(packet, **inputs)


@pytest.mark.parametrize("field", ["history", "bindings"])
def test_verified_consumer_rejects_non_sequence_sources(field):
    packet, history, bindings = _case()
    inputs = {
        "history": history,
        "bindings": bindings,
        "current_environment_fingerprint": ENVIRONMENT_FINGERPRINT,
    }
    inputs[field] = "not-a-record-sequence"

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="must be a list or tuple",
    ):
        consume_verified_situated_reconstruction_packet(packet, **inputs)


def test_verified_consumer_rejects_extra_binding():
    packet, history, bindings = _case()
    extra = bindings + [_binding("unrelated-claim")]

    with pytest.raises(SituatedReconstructionPacketError):
        consume_verified_situated_reconstruction_packet(
            packet,
            history=history,
            bindings=extra,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )


@pytest.mark.parametrize("fingerprint", ["", "   ", None])
def test_verified_consumer_rejects_invalid_current_environment(fingerprint):
    packet, history, bindings = _case()

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="current environment fingerprint mismatch",
    ):
        consume_verified_situated_reconstruction_packet(
            packet,
            history=history,
            bindings=bindings,
            current_environment_fingerprint=fingerprint,
        )


def test_verified_consumer_wraps_unexpected_projection_error(monkeypatch):
    packet, history, bindings = _case()

    import holosim.invariant_validity_lifecycle as lifecycle

    def broken_projection(*args, **kwargs):
        raise RuntimeError("injected projection failure")

    monkeypatch.setattr(
        lifecycle,
        "project_active_invariants",
        broken_projection,
    )

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="unexpected validity history verification failure",
    ) as caught:
        consume_verified_situated_reconstruction_packet(
            packet,
            history=history,
            bindings=bindings,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )

    assert isinstance(caught.value.__cause__, RuntimeError)


def test_verified_consumer_wraps_unexpected_builder_error(monkeypatch):
    packet, history, bindings = _case()

    import holosim.situated_reconstruction_packet as module

    def broken_builder(*args, **kwargs):
        raise RuntimeError("injected builder failure")

    monkeypatch.setattr(
        module,
        "build_situated_reconstruction_packet",
        broken_builder,
    )

    with pytest.raises(
        SituatedReconstructionPacketError,
        match="unexpected reconstruction verification failure",
    ) as caught:
        consume_verified_situated_reconstruction_packet(
            packet,
            history=history,
            bindings=bindings,
            current_environment_fingerprint=ENVIRONMENT_FINGERPRINT,
        )

    assert isinstance(caught.value.__cause__, RuntimeError)
