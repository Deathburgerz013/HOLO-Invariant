import copy

import pytest

from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)
from holosim.state_transfer import (
    StateTransferError,
    build_state_transfer,
    observe_state_transfer,
    validate_state_transfer,
)


def _items():
    return [
        {"id": "a", "requires": ["b"], "value": "target"},
        {"id": "b", "requires": ["c"], "value": "middle"},
        {"id": "c", "requires": [], "value": "base"},
        {"id": "x", "requires": [], "value": "unrelated"},
    ]


def _sender():
    return {
        "provider_label": "test-provider",
        "model_label": "test-model",
        "model_version": "1",
        "interface": "pytest",
    }


def _evidence():
    return {
        "commands": [],
        "observed_results": [],
        "artifact_hashes": {},
        "execution_status": "NOT_RUN",
    }


def test_reconstructed_state_crosses_transfer_boundary_exactly():
    items = _items()
    reconstructed = build_reconstructed_state("target a", ["a"], items)
    validate_reconstructed_state(reconstructed, items)

    envelope = build_state_transfer(
        transfer_id="reconstruction-transfer-1",
        base_snapshot={"receiver": "fresh-instance"},
        payload=reconstructed,
        applied_invariant_ids=["explicit-dependency-reconstruction"],
        evidence=_evidence(),
        declared_sender=_sender(),
    )

    validate_state_transfer(envelope)

    assert envelope["payload"] == reconstructed
    assert envelope["payload"]["reachable_ids"] == ["a", "b", "c"]
    assert [item["id"] for item in envelope["payload"]["carried_items"]] == [
        "a",
        "b",
        "c",
    ]
    assert "x" not in envelope["payload"]["reachable_ids"]
    assert all(item["id"] != "x" for item in envelope["payload"]["carried_items"])
    assert envelope["accepted"] is False
    assert envelope["write_authority"] == "NONE"
    assert envelope["application_status"] == "NOT_APPLIED"


def test_transfer_payload_is_a_copy_not_a_shared_mutable_reference():
    reconstructed = build_reconstructed_state("target a", ["a"], _items())
    envelope = build_state_transfer(
        transfer_id="reconstruction-transfer-2",
        base_snapshot={"receiver": "fresh-instance"},
        payload=reconstructed,
        applied_invariant_ids=["explicit-dependency-reconstruction"],
        evidence=_evidence(),
        declared_sender=_sender(),
    )

    reconstructed["carried_items"][0]["value"] = "mutated-after-transfer"

    assert envelope["payload"]["carried_items"][0]["value"] == "target"
    validate_state_transfer(envelope)


def test_tampering_with_reconstructed_payload_breaks_transfer_validation():
    envelope = build_state_transfer(
        transfer_id="reconstruction-transfer-3",
        base_snapshot={"receiver": "fresh-instance"},
        payload=build_reconstructed_state("target a", ["a"], _items()),
        applied_invariant_ids=["explicit-dependency-reconstruction"],
        evidence=_evidence(),
        declared_sender=_sender(),
    )
    tampered = copy.deepcopy(envelope)
    tampered["payload"]["carried_items"][0]["value"] = "tampered"

    with pytest.raises(StateTransferError, match="payload hash mismatch"):
        validate_state_transfer(tampered)


def test_receiver_observation_does_not_apply_or_accept_reconstructed_payload():
    base = {"receiver": "fresh-instance", "state": "before"}
    envelope = build_state_transfer(
        transfer_id="reconstruction-transfer-4",
        base_snapshot=base,
        payload=build_reconstructed_state("target a", ["a"], _items()),
        applied_invariant_ids=["explicit-dependency-reconstruction"],
        evidence=_evidence(),
        declared_sender=_sender(),
    )

    observation = observe_state_transfer(
        envelope,
        receiver_snapshot=copy.deepcopy(base),
        known_state_hashes=[],
    )

    assert observation["state_status"] == "CURRENT"
    assert observation["payload_applied"] is False
    assert observation["accepted"] is False
    assert observation["write_authority"] == "NONE"


def test_incomplete_reconstruction_remains_incomplete_through_transfer():
    items = [{"id": "a", "requires": ["missing"], "value": "target"}]
    reconstructed = build_reconstructed_state("target a", ["a"], items)

    assert reconstructed["status"] == "INCOMPLETE"
    assert reconstructed["missing_ids"] == ["missing"]

    envelope = build_state_transfer(
        transfer_id="reconstruction-transfer-5",
        base_snapshot={"receiver": "fresh-instance"},
        payload=reconstructed,
        applied_invariant_ids=["explicit-dependency-reconstruction"],
        evidence=_evidence(),
        declared_sender=_sender(),
    )

    validate_state_transfer(envelope)
    assert envelope["payload"]["status"] == "INCOMPLETE"
    assert envelope["payload"]["missing_ids"] == ["missing"]
