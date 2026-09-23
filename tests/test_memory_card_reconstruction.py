from copy import deepcopy

import pytest

from holosim.detection_receipts import build_detection_receipt
from holosim.memory_card import (
    MemoryCardError,
    build_memory_card,
    verify_memory_card,
)
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


def _comparison() -> dict:
    return {
        "type": "baseline_observation_comparison",
        "version": 1,
        "baseline_id": "baseline-1",
        "baseline_state_hash": "a" * 64,
        "left_observation_id": "left",
        "right_observation_id": "right",
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


def _memory_card() -> dict:
    receipt = build_detection_receipt(comparison=_comparison())

    return build_memory_card(
        card_id="memory-card:reconstruction:v1",
        observation=receipt,
        source={
            "kind": "detection_receipt",
            "receipt_hash": receipt["receipt_hash"],
        },
    )


def test_memory_card_reconstructs_same_state_after_boundary_crossing():
    card = _memory_card()

    original_items = [
        {
            "id": "memory",
            "requires": [],
            "memory_card": card,
        }
    ]

    transported = deepcopy(card)
    assert verify_memory_card(transported) is True

    transported_items = [
        {
            "id": "memory",
            "requires": [],
            "memory_card": transported,
        }
    ]

    original_state = build_reconstructed_state(
        "memory-card-boundary",
        ["memory"],
        original_items,
    )

    transported_state = build_reconstructed_state(
        "memory-card-boundary",
        ["memory"],
        transported_items,
    )

    assert validate_reconstructed_state(
        original_state,
        original_items,
    ) is True

    assert validate_reconstructed_state(
        transported_state,
        transported_items,
    ) is True

    assert original_state["state_hash"] == transported_state["state_hash"]


def test_memory_card_reconstruction_rejects_changed_history():
    card = _memory_card()

    changed = deepcopy(card)
    changed["corrections"].append(
        {
            "correction_id": "later-correction",
            "source_receipt_hash": card["observation"]["receipt_hash"],
            "statement": "Later evidence requires rechecking.",
        }
    )

    # The original card remains independently valid.
    assert verify_memory_card(card) is True

    # The changed contents still carry the old identity and therefore
    # must fail the memory-card verification gate.
    assert changed["card_hash"] == card["card_hash"]

    with pytest.raises(MemoryCardError):
        verify_memory_card(changed)