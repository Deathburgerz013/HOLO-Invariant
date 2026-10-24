from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.baseline_observation_compare import (
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.detection_receipts import (
    DetectionReceiptError,
    build_detection_receipt,
    verify_detection_receipt,
)


def _evidence():
    left = build_baseline_observation(
        observer_id="observer-a",
        baseline_id="baseline-1",
        baseline_state_hash="state-a",
        findings={"claim-1": "SUPPORT"},
    )
    right = build_baseline_observation(
        observer_id="observer-b",
        baseline_id="baseline-1",
        baseline_state_hash="state-a",
        findings={"claim-1": "CORRECTION"},
    )
    comparison = compare_baseline_observations(left, right)
    comparison.pop("comparison_id")
    receipt = build_detection_receipt(comparison=comparison)
    return left, right, comparison, receipt


def test_real_conflict_verifies_with_original_observations():
    left, right, comparison, receipt = _evidence()

    assert receipt["detected"] is True
    assert receipt["discrepancies"] == ["claim-1"]

    assert verify_detection_receipt(
        receipt,
        comparison=comparison,
        left_observation=left,
        right_observation=right,
    ) is True


def test_fabricated_agreement_rejected_with_original_observations():
    left, right, comparison, _ = _evidence()

    fabricated = deepcopy(comparison)
    fabricated["per_claim"]["claim-1"]["classification"] = "AGREEMENT"
    fabricated["agreement"] = ["claim-1"]
    fabricated["conflict"] = []

    receipt = build_detection_receipt(comparison=fabricated)

    assert receipt["detected"] is False

    # Legacy comparison-only verification remains intentionally available.
    assert verify_detection_receipt(
        receipt,
        comparison=fabricated,
    ) is True

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=fabricated,
            left_observation=left,
            right_observation=right,
        )


@pytest.mark.parametrize("side", ["left", "right"])
def test_partial_source_evidence_fails_closed(side):
    left, right, comparison, receipt = _evidence()

    kwargs = {
        "left_observation": left,
    } if side == "left" else {
        "right_observation": right,
    }

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=comparison,
            **kwargs,
        )


def test_explicit_none_is_not_treated_as_omission():
    left, right, comparison, receipt = _evidence()

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=comparison,
            left_observation=None,
            right_observation=right,
        )


def test_reversed_observations_fail_closed():
    left, right, comparison, receipt = _evidence()

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=comparison,
            left_observation=right,
            right_observation=left,
        )


def test_modified_observation_body_fails_closed():
    left, right, comparison, receipt = _evidence()

    modified = deepcopy(left)
    modified["findings"]["claim-1"] = "CORRECTION"

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=comparison,
            left_observation=modified,
            right_observation=right,
        )


def test_mismatched_baseline_fails_closed():
    left, right, comparison, receipt = _evidence()

    other = build_baseline_observation(
        observer_id="observer-b",
        baseline_id="different-baseline",
        baseline_state_hash="state-a",
        findings={"claim-1": "CORRECTION"},
    )

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=comparison,
            left_observation=left,
            right_observation=other,
        )


def test_historical_comparison_without_id_verifies():
    left, right, comparison, _ = _evidence()

    historical = deepcopy(comparison)
    assert "comparison_id" not in historical

    receipt = build_detection_receipt(comparison=historical)

    assert verify_detection_receipt(
        receipt,
        comparison=historical,
        left_observation=left,
        right_observation=right,
    ) is True


def test_comparison_id_is_not_part_of_detection_receipt_schema():
    left, right, comparison, receipt = _evidence()

    fabricated = deepcopy(comparison)
    fabricated["comparison_id"] = "fabricated"

    with pytest.raises(DetectionReceiptError):
        verify_detection_receipt(
            receipt,
            comparison=fabricated,
            left_observation=left,
            right_observation=right,
        )


def test_verified_receipt_grants_no_authority():
    left, right, comparison, receipt = _evidence()

    assert verify_detection_receipt(
        receipt,
        comparison=comparison,
        left_observation=left,
        right_observation=right,
    ) is True

    assert receipt["resolved"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
