"""Bind a verified current time-scoped observation to a contradiction challenge target."""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import stable_hash
from holosim.time_scoped_truth import verify_time_scoped_truth_receipt
from holosim.bounded_contradiction_challenge import verify_bounded_contradiction_challenge_receipt


RECEIPT_TYPE = "current_observation_challenge_binding_receipt"
RECEIPT_VERSION = 1


class CurrentObservationChallengeBindingError(ValueError):
    """Raised when current observation and challenge cannot be bound safely."""


def bind_current_observation_to_challenge(
    *,
    current_truth_receipt: Mapping[str, Any],
    challenge_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a verified observation state identity to one verified challenge target."""
    try:
        verify_time_scoped_truth_receipt(current_truth_receipt)
    except Exception as exc:
        raise CurrentObservationChallengeBindingError(
            f"current truth receipt is invalid: {exc}"
        ) from exc

    try:
        challenge_verification = verify_bounded_contradiction_challenge_receipt(
            challenge_receipt
        )
    except Exception as exc:
        raise CurrentObservationChallengeBindingError(
            f"challenge receipt is invalid: {exc}"
        ) from exc

    if challenge_verification.get("valid") is not True:
        raise CurrentObservationChallengeBindingError(
            "challenge receipt did not verify"
        )

    observed_state_hash = current_truth_receipt["observation"]["state_hash"]
    challenge_target_state_hash = challenge_receipt["target_state_hash"]
    identity_matches = observed_state_hash == challenge_target_state_hash

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "current_truth_receipt_hash": current_truth_receipt["receipt_hash"],
        "challenge_receipt_id": challenge_receipt["receipt_id"],
        "observed_state_hash": observed_state_hash,
        "challenge_target_state_hash": challenge_target_state_hash,
        "identity_matches": identity_matches,
        "status": "BOUND" if identity_matches else "IDENTITY_MISMATCH",
        "binding_complete": identity_matches,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "BOUND establishes only that the verified time-scoped observation "
            "and verified contradiction challenge name the same state identity. "
            "It does not establish truth, absence of contradiction, continuation "
            "admissibility, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_current_observation_challenge_binding_receipt(
    receipt: Mapping[str, Any],
    *,
    current_truth_receipt: Mapping[str, Any],
    challenge_receipt: Mapping[str, Any],
) -> bool:
    """Regenerate the binding from its evidence and require exact equality."""
    if type(receipt) is not dict:
        raise CurrentObservationChallengeBindingError(
            "binding receipt must be a plain dictionary"
        )

    expected_fields = {
        "type",
        "version",
        "current_truth_receipt_hash",
        "challenge_receipt_id",
        "observed_state_hash",
        "challenge_target_state_hash",
        "identity_matches",
        "status",
        "binding_complete",
        "truth_claimed",
        "accepted",
        "write_authority",
        "execution_authority",
        "interpretation_notice",
        "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise CurrentObservationChallengeBindingError(
            "binding receipt fields do not match the versioned schema"
        )

    if receipt.get("type") != RECEIPT_TYPE or receipt.get("version") != RECEIPT_VERSION:
        raise CurrentObservationChallengeBindingError(
            "binding receipt type or version is invalid"
        )

    if (
        receipt.get("truth_claimed") is not False
        or receipt.get("accepted") is not False
        or receipt.get("write_authority") != "NONE"
        or receipt.get("execution_authority") != "NONE"
    ):
        raise CurrentObservationChallengeBindingError(
            "binding receipt cannot grant authority"
        )

    expected = bind_current_observation_to_challenge(
        current_truth_receipt=current_truth_receipt,
        challenge_receipt=challenge_receipt,
    )
    if dict(receipt) != expected:
        raise CurrentObservationChallengeBindingError(
            "binding receipt does not match supplied evidence"
        )

    return True
