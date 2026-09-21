"""Verified continuity across observer absence."""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import stable_hash


class ContinuityUnderAbsenceError(ValueError):
    """Raised when continuity evidence is malformed or unverifiable."""


def build_continuity_receipt(
    *,
    prior_state: Mapping[str, Any],
    current_state: Mapping[str, Any],
    observer_present_before: bool,
    observer_present_after: bool,
) -> dict[str, Any]:
    if observer_present_before is not True:
        raise ContinuityUnderAbsenceError(
            "prior state requires an observed starting boundary"
        )
    if observer_present_after is not False:
        raise ContinuityUnderAbsenceError(
            "continuity-under-absence requires observer absence"
        )
    if type(prior_state) is not dict or type(current_state) is not dict:
        raise ContinuityUnderAbsenceError("states must be dictionaries")

    body = {
        "type": "continuity_under_absence_receipt",
        "version": 1,
        "prior_state": dict(prior_state),
        "current_state": dict(current_state),
        "prior_state_hash": stable_hash(prior_state),
        "current_state_hash": stable_hash(current_state),
        "observer_present_before": True,
        "observer_present_after": False,
        "continuity_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}



def verify_continuity_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild the closed receipt and reject semantic tampering."""
    expected_fields = {
        "type",
        "version",
        "prior_state",
        "current_state",
        "prior_state_hash",
        "current_state_hash",
        "observer_present_before",
        "observer_present_after",
        "continuity_claimed",
        "truth_claimed",
        "accepted",
        "write_authority",
        "execution_authority",
        "receipt_hash",
    }
    if type(receipt) is not dict or set(receipt) != expected_fields:
        raise ContinuityUnderAbsenceError("receipt fields mismatch")

    if receipt["type"] != "continuity_under_absence_receipt":
        raise ContinuityUnderAbsenceError("receipt schema mismatch")
    if receipt["version"] != 1:
        raise ContinuityUnderAbsenceError("receipt schema mismatch")

    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if stable_hash(body) != receipt["receipt_hash"]:
        raise ContinuityUnderAbsenceError("receipt hash mismatch")

    expected = build_continuity_receipt(
        prior_state=receipt["prior_state"],
        current_state=receipt["current_state"],
        observer_present_before=receipt["observer_present_before"],
        observer_present_after=receipt["observer_present_after"],
    )

    if dict(receipt) != expected:
        raise ContinuityUnderAbsenceError("receipt is internally inconsistent")

    return True



def reconstruct_continuity(
    receipt: Mapping[str, Any],
    *,
    external_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Reconstruct a bounded transition only from verified external evidence."""
    verify_continuity_receipt(receipt)

    if external_evidence is None:
        raise ContinuityUnderAbsenceError(
            "continuity reconstruction requires verified external evidence"
        )

    raise ContinuityUnderAbsenceError(
        "external evidence is not yet supported"
    )





