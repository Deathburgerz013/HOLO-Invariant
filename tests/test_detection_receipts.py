from __future__ import annotations

import copy

import pytest

from holosim.detection_receipts import (
    DetectionReceiptError,
    build_detection_receipt,
    verify_detection_receipt,
)


def _comparison():
    return {
        "type": "baseline_observation_comparison",
        "version": 1,
        "baseline_id": "baseline-1",
        "baseline_state_hash": "state-a",
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


def test_detection_receipt_records_discrepancy_without_resolving_it():
    comparison = _comparison()

    receipt = build_detection_receipt(
        comparison=comparison,
    )

    assert receipt["type"] == "detection_receipt"
    assert receipt["version"] == 1
    assert receipt["detected"] is True
    assert receipt["discrepancies"] == ["claim-1"]
    assert receipt["resolved"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert isinstance(receipt["receipt_hash"], str)
    assert len(receipt["receipt_hash"]) == 64


def test_detection_receipt_is_deterministic():
    comparison = _comparison()

    first = build_detection_receipt(comparison=comparison)
    second = build_detection_receipt(comparison=comparison)

    assert first == second


def test_detection_receipt_verifies():
    receipt = build_detection_receipt(
        comparison=_comparison(),
    )

    assert verify_detection_receipt(receipt, comparison=_comparison()) is True


def test_tampered_detection_receipt_fails_closed():
    receipt = build_detection_receipt(
        comparison=_comparison(),
    )

    tampered = copy.deepcopy(receipt)
    tampered["resolved"] = True

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            tampered,
            comparison=_comparison(),
        )


def test_tampered_comparison_fails_closed():
    comparison = _comparison()
    receipt = build_detection_receipt(comparison=comparison)

    tampered = copy.deepcopy(comparison)
    tampered["conflict"] = []

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=tampered,
        )