import copy

import pytest

from holosim.detection_receipts import (
    DetectionReceiptError,
    build_detection_receipt,
    verify_detection_receipt,
)


def _comparison(
    *,
    left_observation_id="left",
    right_observation_id="right",
    conflict=True,
):
    return {
        "type": "baseline_observation_comparison",
        "version": 1,
        "baseline_id": "baseline-1",
        "baseline_state_hash": "state-a",
        "left_observation_id": left_observation_id,
        "right_observation_id": right_observation_id,
        "observer_ids": ["observer-a", "observer-b"],
        "per_claim": {
            "claim-1": {
                "claim_id": "claim-1",
                "left": "SUPPORT",
                "right": "CORRECTION",
                "classification": "CONFLICT" if conflict else "AGREEMENT",
            }
        },
        "agreement": [] if conflict else ["claim-1"],
        "extension": [],
        "correction": [],
        "conflict": ["claim-1"] if conflict else [],
        "unknown": [],
        "next_baseline_selected": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def test_detection_receipt_verifies_against_same_comparison():
    original = _comparison()
    receipt = build_detection_receipt(comparison=original)

    assert verify_detection_receipt(
        receipt,
        comparison=original,
    ) is True


def test_detection_receipt_rejects_fresh_observation_identity():
    original = _comparison()
    receipt = build_detection_receipt(comparison=original)

    fresh = _comparison(
        left_observation_id="left-fresh",
        right_observation_id="right-fresh",
    )

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=fresh,
        )


def test_detection_receipt_rejects_changed_detection_outcome():
    original = _comparison()
    receipt = build_detection_receipt(comparison=original)

    fresh = _comparison(
        left_observation_id="left-fresh",
        right_observation_id="right-fresh",
        conflict=False,
    )

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=fresh,
        )