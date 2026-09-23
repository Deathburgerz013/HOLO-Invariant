"""Fail-closed discrepancy detection over verified baseline comparisons."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.baseline_observation_compare import (
    BaselineObservationError,
    compare_baseline_observations,
)
from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "detection_receipt"
RECEIPT_VERSION = 1

_ALLOWED_DISCREPANCY_CLASSES = {
    "CORRECTION",
    "CONFLICT",
    "EXTENSION",
    "UNKNOWN",
}


class DetectionReceiptError(ValueError):
    """Raised when a detection receipt or its source comparison is invalid."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise DetectionReceiptError(str(exc)) from exc


def _validate_comparison(
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    if type(comparison) is not dict:
        raise DetectionReceiptError("comparison must be a plain dictionary")

    required = {
        "type",
        "version",
        "baseline_id",
        "baseline_state_hash",
        "left_observation_id",
        "right_observation_id",
        "observer_ids",
        "per_claim",
        "agreement",
        "extension",
        "correction",
        "conflict",
        "unknown",
        "next_baseline_selected",
        "truth_claimed",
        "accepted",
        "write_authority",
    }

    if set(comparison) != required:
        raise DetectionReceiptError(
            "comparison fields do not match the expected schema"
        )

    if comparison["type"] != "baseline_observation_comparison":
        raise DetectionReceiptError("comparison type is invalid")

    if comparison["version"] != 1:
        raise DetectionReceiptError("comparison version is invalid")

    if comparison["next_baseline_selected"] is not False:
        raise DetectionReceiptError(
            "comparison must not select a next baseline"
        )

    if comparison["truth_claimed"] is not False:
        raise DetectionReceiptError(
            "comparison must not claim truth"
        )

    if comparison["accepted"] is not False:
        raise DetectionReceiptError(
            "comparison must not be accepted"
        )

    if comparison["write_authority"] != "NONE":
        raise DetectionReceiptError(
            "comparison must not have write authority"
        )

    return deepcopy(comparison)


def _rebuild_comparison(comparison: Mapping[str, Any]) -> dict[str, Any]:
    try:
        left = comparison["left_observation_id"]
        right = comparison["right_observation_id"]
        per_claim = comparison["per_claim"]

        if not isinstance(per_claim, Mapping):
            raise DetectionReceiptError("comparison per_claim must be an object")

        # The comparison itself carries observation IDs but not the original
        # observation bodies, so structural validation is performed here.
        if not isinstance(left, str) or not left.strip():
            raise DetectionReceiptError("left_observation_id is invalid")

        if not isinstance(right, str) or not right.strip():
            raise DetectionReceiptError("right_observation_id is invalid")

        for claim_id, entry in per_claim.items():
            if not isinstance(claim_id, str) or not claim_id.strip():
                raise DetectionReceiptError("comparison claim id is invalid")

            if not isinstance(entry, Mapping):
                raise DetectionReceiptError(
                    f"comparison claim {claim_id!r} must be an object"
                )

            required_entry = {
                "claim_id",
                "left",
                "right",
                "classification",
            }

            if set(entry) != required_entry:
                raise DetectionReceiptError(
                    f"comparison claim {claim_id!r} fields are invalid"
                )

            if entry["claim_id"] != claim_id:
                raise DetectionReceiptError(
                    f"comparison claim {claim_id!r} identity mismatch"
                )

            if entry["classification"] not in _ALLOWED_DISCREPANCY_CLASSES | {
                "AGREEMENT"
            }:
                raise DetectionReceiptError(
                    f"comparison claim {claim_id!r} classification is invalid"
                )

        return deepcopy(dict(comparison))

    except KeyError as exc:
        raise DetectionReceiptError(
            f"comparison is missing field: {exc.args[0]}"
        ) from exc


def build_detection_receipt(
    *,
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    """Register discrepancies present in one bounded comparison.

    Detection records what the comparison already exposes. It does not resolve
    discrepancies, select truth, accept evidence, mutate a baseline, or grant
    authority.
    """
    checked = _validate_comparison(comparison)
    checked = _rebuild_comparison(checked)

    discrepancies = sorted(
        set(checked["conflict"])
        | set(checked["correction"])
        | set(checked["extension"])
    )

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "comparison_hash": _hash(checked),
        "baseline_id": checked["baseline_id"],
        "baseline_state_hash": checked["baseline_state_hash"],
        "discrepancies": discrepancies,
        "detected": bool(discrepancies),
        "resolved": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": _hash(body),
    }


def verify_detection_receipt(
    receipt: Mapping[str, Any],
    *,
    comparison: Mapping[str, Any],
) -> bool:
    """Verify a detection receipt against its exact source comparison."""
    if type(receipt) is not dict:
        raise DetectionReceiptError("receipt must be a plain dictionary")

    required = {
        "type",
        "version",
        "comparison_hash",
        "baseline_id",
        "baseline_state_hash",
        "discrepancies",
        "detected",
        "resolved",
        "truth_claimed",
        "accepted",
        "write_authority",
        "execution_authority",
        "receipt_hash",
    }

    if set(receipt) != required:
        raise DetectionReceiptError(
            "receipt fields do not match the expected schema"
        )

    checked = _validate_comparison(comparison)
    checked = _rebuild_comparison(checked)

    expected = build_detection_receipt(comparison=checked)

    if dict(receipt) != expected:
        raise DetectionReceiptError(
            "detection receipt does not match its source comparison"
        )

    return True