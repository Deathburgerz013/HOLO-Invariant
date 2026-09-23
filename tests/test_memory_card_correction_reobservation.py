from copy import deepcopy

from holosim.detection_receipts import build_detection_receipt
from holosim.memory_card import build_memory_card, verify_memory_card


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
        card_id="memory-card:correction-reobservation:v1",
        observation=receipt,
        source={
            "kind": "detection_receipt",
            "receipt_hash": receipt["receipt_hash"],
        },
    )


def test_memory_card_preserves_original_when_correction_and_reobservation_are_added():
    card = _memory_card()
    original_observation = deepcopy(card["observation"])

    correction = {
        "type": "correction",
        "correction_id": "correction-1",
        "source_receipt_hash": original_observation["receipt_hash"],
        "statement": "The discrepancy remains unresolved.",
    }

    reobservation = {
        "type": "reobservation",
        "reobservation_id": "reobservation-1",
        "source_receipt_hash": original_observation["receipt_hash"],
        "status": "REOBSERVATION_UNRESOLVED",
    }

    updated = deepcopy(card)
    updated["corrections"] = [correction]
    updated["reobservations"] = [reobservation]

    assert updated["observation"] == original_observation
    assert (
        updated["observation"]["receipt_hash"]
        == original_observation["receipt_hash"]
    )

    assert (
        correction["source_receipt_hash"]
        == original_observation["receipt_hash"]
    )
    assert (
        reobservation["source_receipt_hash"]
        == original_observation["receipt_hash"]
    )

    assert updated["card_hash"] == card["card_hash"]

    try:
        verify_memory_card(updated)
    except Exception:
        pass
    else:
        raise AssertionError(
            "adding later history without recomputing identity must fail closed"
        )


def test_memory_card_history_is_append_only_from_the_original_observation():
    card = _memory_card()

    original_hash = card["observation"]["receipt_hash"]
    original_observation = deepcopy(card["observation"])

    history = [
        {
            "type": "correction",
            "correction_id": "correction-1",
            "source_receipt_hash": original_hash,
            "statement": "The original discrepancy remains unresolved.",
        },
        {
            "type": "reobservation",
            "reobservation_id": "reobservation-1",
            "source_receipt_hash": original_hash,
            "status": "REOBSERVATION_UNRESOLVED",
        },
    ]

    updated = deepcopy(card)
    updated["corrections"] = [history[0]]
    updated["reobservations"] = [history[1]]

    assert updated["observation"] == original_observation
    assert updated["observation"]["receipt_hash"] == original_hash

    assert updated["corrections"][0]["source_receipt_hash"] == original_hash
    assert (
        updated["reobservations"][0]["source_receipt_hash"]
        == original_hash
    )

    # The historical additions cannot silently become part of the original
    # observation merely by being attached to the memory card.
    assert updated["observation"] != updated["corrections"][0]
    assert updated["observation"] != updated["reobservations"][0]