from copy import deepcopy

import pytest

from holosim.detection_receipts import (
    build_detection_receipt,
    verify_detection_receipt,
)
from holosim.memory_card import (
    MemoryCardError,
    build_memory_card,
    verify_memory_card,
)


def _comparison(observed: str = "right") -> dict:
    return {
        "type": "baseline_observation_comparison",
        "version": 1,
        "baseline_id": "baseline-1",
        "baseline_state_hash": "a" * 64,
        "left_observation_id": "left",
        "right_observation_id": observed,
        "observer_ids": ["observer-a", "observer-b"],
        "per_claim": {
            "claim-1": {
                "claim_id": "claim-1",
                "left": "SUPPORT",
                "right": "CORRECTION",
                "classification": "CONFLICT",
            }
        },
        "agreement": [],
        "extension": [],
        "correction": [],
        "conflict": ["claim-1"],
        "unknown": [],
        "next_baseline_selected": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def test_memory_card_preserves_verified_receipt_identity_across_boundary():
    comparison = _comparison()
    receipt = build_detection_receipt(comparison=comparison)

    card = build_memory_card(
        card_id="memory-card:detection:v1",
        observation=receipt,
        source={
            "kind": "detection_receipt",
            "receipt_type": receipt["type"],
            "receipt_hash": receipt["receipt_hash"],
        },
    )

    transported = deepcopy(card)

    assert verify_memory_card(transported) is True
    assert verify_detection_receipt(
        transported["observation"],
        comparison=comparison,
    ) is True

    assert transported["observation_hash"] == card["observation_hash"]
    assert transported["observation"]["receipt_hash"] == receipt["receipt_hash"]
    assert transported["source"]["receipt_hash"] == receipt["receipt_hash"]


def test_memory_card_carries_correction_and_reobservation_without_rewriting_observation():
    comparison = _comparison()
    receipt = build_detection_receipt(comparison=comparison)

    correction = {
        "type": "correction",
        "correction_id": "correction-1",
        "source_receipt_hash": receipt["receipt_hash"],
        "statement": "The original discrepancy remains unresolved.",
    }

    reobservation = {
        "type": "reobservation",
        "reobservation_id": "reobservation-1",
        "source_receipt_hash": receipt["receipt_hash"],
        "status": "REOBSERVATION_UNRESOLVED",
    }

    card = build_memory_card(
        card_id="memory-card:detection:v1",
        observation=receipt,
        source={
            "kind": "detection_receipt",
            "receipt_hash": receipt["receipt_hash"],
        },
        corrections=[correction],
        reobservations=[reobservation],
    )

    assert verify_memory_card(card) is True
    assert card["observation"]["receipt_hash"] == receipt["receipt_hash"]
    assert (
        card["corrections"][0]["source_receipt_hash"]
        == receipt["receipt_hash"]
    )
    assert (
        card["reobservations"][0]["source_receipt_hash"]
        == receipt["receipt_hash"]
    )


def test_memory_card_boundary_tampering_is_detectable():
    receipt = build_detection_receipt(comparison=_comparison())

    card = build_memory_card(
        card_id="memory-card:detection:v1",
        observation=receipt,
        source={
            "kind": "detection_receipt",
            "receipt_hash": receipt["receipt_hash"],
        },
    )

    tampered = deepcopy(card)
    tampered["observation"]["detected"] = False

    with pytest.raises(MemoryCardError):
        verify_memory_card(tampered)


def test_memory_card_does_not_grant_authority():
    receipt = build_detection_receipt(comparison=_comparison())

    card = build_memory_card(
        card_id="memory-card:detection:v1",
        observation=receipt,
        source={
            "kind": "detection_receipt",
            "receipt_hash": receipt["receipt_hash"],
        },
    )

    assert card["observation"]["accepted"] is False
    assert card["observation"]["write_authority"] == "NONE"
    assert card["observation"]["execution_authority"] == "NONE"