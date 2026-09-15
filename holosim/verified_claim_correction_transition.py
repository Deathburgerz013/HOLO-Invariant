"""Bind verified claim improvement to one exact baseline transition candidate."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.authorized_baseline_transition import (
    AuthorizedBaselineTransitionError,
    build_baseline_transition_candidate,
)
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.evidence_bound_claim_correction_verification import (
    EvidenceBoundClaimCorrectionVerificationError,
    STATUS_VERIFIED,
    validate_evidence_bound_claim_correction_verification,
)
from holosim.typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
)

TRANSITION_BINDING_TYPE = "verified_claim_correction_transition_candidate"
TRANSITION_BINDING_VERSION = 1
STATUS_READY = "READY_FOR_EXACT_TARGET_AUTHORIZATION"

TRANSITION_BINDING_FIELDS = {
    "type",
    "version",
    "verification",
    "verification_hash",
    "proposal_hash",
    "promotion_gate_id",
    "previous_baseline_id",
    "previous_baseline_state_hash",
    "next_baseline_id",
    "next_baseline_state_hash",
    "corrected_claim_ids",
    "condition_ids",
    "newly_solved",
    "preserved",
    "baseline_transition_candidate",
    "authorization_action",
    "authorization_target_sha256",
    "status",
    "transition_candidate_created",
    "authorization_requested",
    "authorization_consumed",
    "transition_created",
    "correction_applied",
    "supersession_performed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "canonical_mutation",
    "interpretation_notice",
    "binding_hash",
}


class VerifiedClaimCorrectionTransitionError(ValueError):
    """Raised when verified improvement cannot bind one transition candidate."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise VerifiedClaimCorrectionTransitionError(str(exc)) from exc


def _validate_verification(
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    if type(verification) is not dict:
        raise VerifiedClaimCorrectionTransitionError(
            "verification must be a plain dictionary"
        )

    try:
        validate_evidence_bound_claim_correction_verification(
            verification
        )
    except EvidenceBoundClaimCorrectionVerificationError as exc:
        raise VerifiedClaimCorrectionTransitionError(
            f"verification is invalid: {exc}"
        ) from exc

    if verification["status"] != STATUS_VERIFIED:
        raise VerifiedClaimCorrectionTransitionError(
            "verification is not ready to request authorization"
        )
    if verification["verification_complete"] is not True:
        raise VerifiedClaimCorrectionTransitionError(
            "verification must be complete"
        )
    if verification["verified_to_request_authorization"] is not True:
        raise VerifiedClaimCorrectionTransitionError(
            "verification does not permit an authorization request"
        )
    if verification["authorization_requested"] is not False:
        raise VerifiedClaimCorrectionTransitionError(
            "verification must not already request authorization"
        )
    if verification["transition_created"] is not False:
        raise VerifiedClaimCorrectionTransitionError(
            "verification must not already create a transition"
        )
    if (
        verification["accepted"] is not False
        or verification["truth_claimed"] is not False
        or verification["write_authority"] != "NONE"
        or verification["execution_authority"] != "NONE"
        or verification["canonical_mutation"] is not False
    ):
        raise VerifiedClaimCorrectionTransitionError(
            "verification cannot grant authority or mutation"
        )

    return deepcopy(verification)


def build_verified_claim_correction_transition_candidate(
    *,
    verification: Mapping[str, Any],
    next_baseline_id: str,
) -> dict[str, Any]:
    """Create one exact authorization target without requesting authorization."""

    checked_verification = _validate_verification(verification)
    proposal = checked_verification["proposal"]
    promotion_gate = proposal["promotion"]["gate"]

    try:
        transition_candidate = build_baseline_transition_candidate(
            promotion_gate=promotion_gate,
            next_baseline_id=next_baseline_id,
            next_baseline_state_hash=checked_verification[
                "candidate_baseline_hash"
            ],
        )
    except AuthorizedBaselineTransitionError as exc:
        raise VerifiedClaimCorrectionTransitionError(str(exc)) from exc

    body = {
        "type": TRANSITION_BINDING_TYPE,
        "version": TRANSITION_BINDING_VERSION,
        "verification": checked_verification,
        "verification_hash": checked_verification["verification_hash"],
        "proposal_hash": proposal["proposal_hash"],
        "promotion_gate_id": promotion_gate["gate_id"],
        "previous_baseline_id": transition_candidate[
            "previous_baseline_id"
        ],
        "previous_baseline_state_hash": transition_candidate[
            "previous_baseline_state_hash"
        ],
        "next_baseline_id": transition_candidate["next_baseline_id"],
        "next_baseline_state_hash": transition_candidate[
            "next_baseline_state_hash"
        ],
        "corrected_claim_ids": list(
            checked_verification["corrected_claim_ids"]
        ),
        "condition_ids": list(checked_verification["condition_ids"]),
        "newly_solved": list(checked_verification["newly_solved"]),
        "preserved": list(checked_verification["preserved"]),
        "baseline_transition_candidate": transition_candidate,
        "authorization_action": ACTION_BASELINE_PROMOTION,
        "authorization_target_sha256": transition_candidate[
            "candidate_hash"
        ],
        "status": STATUS_READY,
        "transition_candidate_created": True,
        "authorization_requested": False,
        "authorization_consumed": False,
        "transition_created": False,
        "correction_applied": False,
        "supersession_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt binds one complete evidence-verified claim "
            "correction to one exact baseline transition candidate and "
            "authorization target. It does not create or consume operational "
            "authorization, perform the transition, accept or apply the "
            "correction, persist or supersede state, establish truth, or "
            "grant write or execution authority."
        ),
    }
    return {**body, "binding_hash": _hash(body)}


def validate_verified_claim_correction_transition_candidate(
    binding: Mapping[str, Any],
) -> bool:
    """Regenerate the binding and require exact schema and identity."""

    if type(binding) is not dict:
        raise VerifiedClaimCorrectionTransitionError(
            "binding must be a plain dictionary"
        )
    if set(binding) != TRANSITION_BINDING_FIELDS:
        raise VerifiedClaimCorrectionTransitionError(
            "binding fields do not match the versioned schema"
        )
    if (
        binding.get("type") != TRANSITION_BINDING_TYPE
        or binding.get("version") != TRANSITION_BINDING_VERSION
    ):
        raise VerifiedClaimCorrectionTransitionError(
            "binding type or version is invalid"
        )

    try:
        rebuilt = build_verified_claim_correction_transition_candidate(
            verification=binding["verification"],
            next_baseline_id=binding["next_baseline_id"],
        )
    except (KeyError, TypeError) as exc:
        raise VerifiedClaimCorrectionTransitionError(
            "binding content is malformed"
        ) from exc

    if rebuilt != binding:
        raise VerifiedClaimCorrectionTransitionError(
            "binding does not match its verified correction"
        )

    return True