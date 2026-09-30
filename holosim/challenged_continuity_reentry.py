"""Compose verified cold-start reentry with a state-bound contradiction challenge."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from holosim.canonical import stable_hash
from holosim.current_observation_challenge_binding import (
    CurrentObservationChallengeBindingError,
    verify_current_observation_challenge_binding_receipt,
)
from holosim.verified_cold_start_reentry_gateway import (
    VerifiedColdStartReentryError,
    validate_verified_cold_start_reentry_packet,
)
from holosim.bounded_contradiction_challenge import (
    CONTRADICTION_FOUND,
    NO_CONTRADICTION_FOUND,
    SEARCH_INSUFFICIENT,
    verify_bounded_contradiction_challenge_receipt,
)

RECEIPT_TYPE = "challenged_continuity_reentry_receipt"
RECEIPT_VERSION = 1


class ChallengedContinuityReentryError(ValueError):
    """Raised when challenged reentry evidence is malformed or unbound."""


def evaluate_challenged_continuity_reentry(
    *,
    reentry_packet: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
    observation_challenge_binding: Mapping[str, Any],
    challenge_receipt: Mapping[str, Any],
    current_truth_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Recheck the supplied observation binding before deciding reentry readiness."""
    if current_truth_receipt is None:
        raise ChallengedContinuityReentryError(
            "current truth receipt is required to verify the binding"
        )
    try:
        validate_verified_cold_start_reentry_packet(
            reentry_packet,
            source_items=source_items,
        )
    except VerifiedColdStartReentryError as exc:
        raise ChallengedContinuityReentryError(
            f"reentry packet is invalid: {exc}"
        ) from exc

    verification = verify_bounded_contradiction_challenge_receipt(
        challenge_receipt
    )
    if verification.get("valid") is not True:
        raise ChallengedContinuityReentryError(
            "challenge receipt did not verify"
        )

    if type(observation_challenge_binding) is not dict:
        raise ChallengedContinuityReentryError(
            "observation challenge binding must be a plain dictionary"
        )

    binding_body = dict(observation_challenge_binding)
    binding_hash = binding_body.pop("receipt_hash", None)
    if binding_hash is None or stable_hash(binding_body) != binding_hash:
        raise ChallengedContinuityReentryError(
            "observation challenge binding hash mismatch"
        )

    if observation_challenge_binding.get("type") != "current_observation_challenge_binding_receipt":
        raise ChallengedContinuityReentryError(
            "observation challenge binding type is invalid"
        )
    if observation_challenge_binding.get("version") != 1:
        raise ChallengedContinuityReentryError(
            "observation challenge binding version is invalid"
        )
    if observation_challenge_binding.get("challenge_receipt_id") != challenge_receipt.get("receipt_id"):
        raise ChallengedContinuityReentryError(
            "binding does not reference supplied challenge"
        )

    try:
        verify_current_observation_challenge_binding_receipt(
            observation_challenge_binding,
            current_truth_receipt=current_truth_receipt,
            challenge_receipt=challenge_receipt,
        )
    except CurrentObservationChallengeBindingError as exc:
        raise ChallengedContinuityReentryError(
            f"observation challenge binding is invalid: {exc}"
        ) from exc

    reasons: list[str] = []

    if reentry_packet["gate_decision"] != "ALLOW":
        reasons.append("base_reentry_blocked")

    if (
        observation_challenge_binding.get("status") != "BOUND"
        or observation_challenge_binding.get("identity_matches") is not True
        or observation_challenge_binding.get("binding_complete") is not True
    ):
        reasons.append("challenge_target_not_bound_to_current_observation")

    if (
        observation_challenge_binding["observed_state_hash"]
        != reentry_packet["reconstructed_state_hash"]
    ):
        reasons.append("current_observation_not_bound_to_reconstructed_state")

    challenge_result = challenge_receipt["result"]
    if challenge_result == CONTRADICTION_FOUND:
        reasons.append("contradiction_found")
    elif challenge_result == SEARCH_INSUFFICIENT:
        reasons.append("contradiction_search_insufficient")
    elif challenge_result != NO_CONTRADICTION_FOUND:
        raise ChallengedContinuityReentryError(
            "challenge result is unsupported"
        )

    decision = "ALLOW" if not reasons else "BLOCK"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "reentry_packet_hash": reentry_packet["packet_hash"],
        "observation_challenge_binding_hash": observation_challenge_binding["receipt_hash"],
        "challenge_receipt_id": challenge_receipt["receipt_id"],
        "challenge_result": challenge_result,
        "decision": decision,
        "reasons": reasons,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "ALLOW means only that the supplied verified reentry packet is ready, "
            "the supplied contradiction challenge is bound to the supplied verified "
            "observation of the same reconstructed state identity, and the declared "
            "completed challenge found no contradiction. "
            "It does not establish global truth, future truth, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_challenged_continuity_reentry_receipt(
    receipt: Mapping[str, Any],
    *,
    reentry_packet: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
    observation_challenge_binding: Mapping[str, Any],
    challenge_receipt: Mapping[str, Any],
    current_truth_receipt: Mapping[str, Any] | None = None,
) -> bool:
    """Regenerate challenged reentry from its evidence and require exact equality."""
    if type(receipt) is not dict:
        raise ChallengedContinuityReentryError(
            "challenged reentry receipt must be a plain dictionary"
        )

    expected_fields = {
        "type",
        "version",
        "reentry_packet_hash",
        "observation_challenge_binding_hash",
        "challenge_receipt_id",
        "challenge_result",
        "decision",
        "reasons",
        "truth_claimed",
        "accepted",
        "write_authority",
        "execution_authority",
        "interpretation_notice",
        "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise ChallengedContinuityReentryError(
            "challenged reentry receipt fields do not match the versioned schema"
        )

    if receipt.get("type") != RECEIPT_TYPE or receipt.get("version") != RECEIPT_VERSION:
        raise ChallengedContinuityReentryError(
            "challenged reentry receipt type or version is invalid"
        )

    if (
        receipt.get("truth_claimed") is not False
        or receipt.get("accepted") is not False
        or receipt.get("write_authority") != "NONE"
        or receipt.get("execution_authority") != "NONE"
    ):
        raise ChallengedContinuityReentryError(
            "challenged reentry receipt cannot grant authority"
        )

    expected = evaluate_challenged_continuity_reentry(
        reentry_packet=reentry_packet,
        source_items=source_items,
        observation_challenge_binding=observation_challenge_binding,
        challenge_receipt=challenge_receipt,
        current_truth_receipt=current_truth_receipt,
    )
    if dict(receipt) != expected:
        raise ChallengedContinuityReentryError(
            "challenged reentry receipt does not match supplied evidence"
        )

    return True
