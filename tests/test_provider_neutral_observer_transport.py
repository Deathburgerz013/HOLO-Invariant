from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.provider_neutral_observer_transport import (
    ProviderNeutralObserverTransportError,
    transport_situated_reconstruction_packet,
    verify_provider_neutral_observer_receipt,
)


def _packet():
    body = {
        "type": "holo_situated_reconstruction_packet",
        "version": 1,
        "environment_fingerprint": "environment:test",
        "projection_hash": "projection:test",
        "history_hash": "history:test",
        "objective": "Independently reconstruct the bounded state.",
        "active_claims": [],
        "excluded_claims": [],
        "unresolved": ["Whether observers interpret the packet equivalently."],
        "required_checks": ["Compare observer receipts without inferring truth."],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    return {**body, "packet_hash": stable_hash(body)}


def test_two_observers_receive_byte_identical_canonical_packet():
    packet = _packet()
    received = []

    def adapter(payload):
        received.append(payload)
        return {"status": "OBSERVED"}

    receipts = transport_situated_reconstruction_packet(
        packet=packet,
        observers=[("gpt:independent", adapter), ("grok:independent", adapter)],
    )

    assert len(received) == 2
    assert received[0] == received[1]
    assert isinstance(received[0], bytes)
    assert {item["packet_hash"] for item in receipts} == {packet["packet_hash"]}
    assert len({item["receipt_hash"] for item in receipts}) == 2


def test_receipts_preserve_packet_and_cannot_grant_authority():
    packet = _packet()
    before = deepcopy(packet)

    receipts = transport_situated_reconstruction_packet(
        packet=packet,
        observers=[
            ("observer:a", lambda _: {"finding": "UNKNOWN"}),
            ("observer:b", lambda _: {"finding": "DISPUTED"}),
        ],
    )

    assert packet == before
    for receipt in receipts:
        assert receipt["accepted"] is False
        assert receipt["truth_claimed"] is False
        assert receipt["write_authority"] == "NONE"
        assert receipt["execution_authority"] == "NONE"
        assert receipt["canonical_mutation"] is False
        assert verify_provider_neutral_observer_receipt(receipt, packet=packet)


def test_receipt_tampering_fails_even_when_response_looks_plausible():
    packet = _packet()
    receipt = transport_situated_reconstruction_packet(
        packet=packet,
        observers=[("observer:a", lambda _: {"finding": "UNKNOWN"})],
    )[0]
    receipt["response"]["finding"] = "VERIFIED"

    with pytest.raises(
        ProviderNeutralObserverTransportError,
        match="receipt hash mismatch",
    ):
        verify_provider_neutral_observer_receipt(receipt, packet=packet)


def test_receipt_cannot_be_replayed_for_another_packet():
    packet = _packet()
    receipt = transport_situated_reconstruction_packet(
        packet=packet,
        observers=[("observer:a", lambda _: {"finding": "UNKNOWN"})],
    )[0]
    other = deepcopy(packet)
    body = {key: value for key, value in other.items() if key != "packet_hash"}
    body["objective"] = "A different objective."
    other = {**body, "packet_hash": stable_hash(body)}

    with pytest.raises(
        ProviderNeutralObserverTransportError,
        match="receipt packet hash mismatch",
    ):
        verify_provider_neutral_observer_receipt(receipt, packet=other)


def test_adapter_cannot_mutate_packet_through_an_external_reference():
    packet = _packet()

    def mutating_adapter(_):
        packet["objective"] = "Mutated outside the transport argument."
        packet_body = {key: value for key, value in packet.items() if key != "packet_hash"}
        packet["packet_hash"] = stable_hash(packet_body)
        return {"finding": "UNKNOWN"}

    with pytest.raises(
        ProviderNeutralObserverTransportError,
        match="mutated the packet",
    ):
        transport_situated_reconstruction_packet(
            packet=packet,
            observers=[("observer:mutating", mutating_adapter)],
        )


def test_duplicate_observer_identity_fails_closed():
    adapter = lambda _: {"finding": "UNKNOWN"}

    with pytest.raises(
        ProviderNeutralObserverTransportError,
        match="observer ids must be unique",
    ):
        transport_situated_reconstruction_packet(
            packet=_packet(),
            observers=[("observer:a", adapter), ("observer:a", adapter)],
        )


def test_non_json_observer_response_fails_closed():
    with pytest.raises(
        ProviderNeutralObserverTransportError,
        match="must contain only JSON values",
    ):
        transport_situated_reconstruction_packet(
            packet=_packet(),
            observers=[("observer:a", lambda _: {"bad": {"not-json"}})],
        )
