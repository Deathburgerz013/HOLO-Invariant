"""Authorize one exact evidence-verified claim-correction transition."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.authorized_baseline_transition import (
    AuthorizedBaselineTransitionError,
    authorize_baseline_transition,
)
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.typed_operational_authorization import (
    OperationalAuthorizationError,
    validate_operational_authorization,
)
from holosim.verified_claim_correction_transition import (
    VerifiedClaimCorrectionTransitionError,
    validate_verified_claim_correction_transition_candidate,
)


AUTHORIZED_BINDING_TYPE = (
    "authorized_verified_claim_correction_transition"
)
AUTHORIZED_BINDING_VERSION = 1
STATUS_AUTHORIZED = "AUTHORIZED_FOR_EXACT_TRANSITION"

AUTHORIZED_BINDING_FIELDS = {
    "type",
    "version",
    "transition_binding",
    "binding_hash",
    "verification_hash",
    "proposal_hash",
    "operational_authorization",
    "authorization_hash",
    "authorized_by_actor_id",
    "authorized_baseline_transition",
    "transition_id",
    "candidate_hash",
    "previous_baseline_id",
    "previous_baseline_state_hash",
    "next_baseline_id",
    "next_baseline_state_hash",
    "status",
    "authorization_requested",
    "authorization_validated",
    "authorization_consumed",
    "transition_created",
    "transition_persisted",
    "correction_applied",
    "supersession_performed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "promotion_authority",
    "canonical_mutation",
    "interpretation_notice",
    "authorization_binding_hash",
}


class AuthorizedVerifiedClaimCorrectionTransitionError(ValueError):
    """A verified correction cannot use the supplied authorization."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            str(exc)
        ) from exc


def _validate_transition_binding(
    transition_binding: Mapping[str, Any],
) -> dict[str, Any]:
    if type(transition_binding) is not dict:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "transition_binding must be a plain dictionary"
        )

    try:
        validate_verified_claim_correction_transition_candidate(
            transition_binding
        )
    except VerifiedClaimCorrectionTransitionError as exc:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            f"transition binding is invalid: {exc}"
        ) from exc

    return deepcopy(transition_binding)


def _validate_authorization(
    authorization: Mapping[str, Any],
    *,
    transition_binding: Mapping[str, Any],
) -> dict[str, Any]:
    if type(authorization) is not dict:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "authorization must be a plain dictionary"
        )

    try:
        validate_operational_authorization(
            authorization,
            expected_action=transition_binding["authorization_action"],
            expected_target_sha256=transition_binding[
                "authorization_target_sha256"
            ],
        )
    except OperationalAuthorizationError as exc:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            f"authorization is invalid: {exc}"
        ) from exc

    return deepcopy(authorization)


def authorize_verified_claim_correction_transition(
    *,
    transition_binding: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate exact authorization and create its transition receipt."""

    checked_binding = _validate_transition_binding(transition_binding)
    checked_authorization = _validate_authorization(
        authorization,
        transition_binding=checked_binding,
    )
    promotion_gate = checked_binding["verification"]["proposal"][
        "promotion"
    ]["gate"]

    try:
        transition = authorize_baseline_transition(
            promotion_gate=promotion_gate,
            candidate=checked_binding["baseline_transition_candidate"],
            authorization=checked_authorization,
            authorization_action=checked_binding["authorization_action"],
        )
    except AuthorizedBaselineTransitionError as exc:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            f"baseline transition authorization failed: {exc}"
        ) from exc

    body = {
        "type": AUTHORIZED_BINDING_TYPE,
        "version": AUTHORIZED_BINDING_VERSION,
        "transition_binding": checked_binding,
        "binding_hash": checked_binding["binding_hash"],
        "verification_hash": checked_binding["verification_hash"],
        "proposal_hash": checked_binding["proposal_hash"],
        "operational_authorization": checked_authorization,
        "authorization_hash": checked_authorization[
            "authorization_hash"
        ],
        "authorized_by_actor_id": checked_authorization["actor_id"],
        "authorized_baseline_transition": transition,
        "transition_id": transition["transition_id"],
        "candidate_hash": transition["candidate_hash"],
        "previous_baseline_id": transition["previous_baseline_id"],
        "previous_baseline_state_hash": transition[
            "previous_baseline_state_hash"
        ],
        "next_baseline_id": transition["next_baseline_id"],
        "next_baseline_state_hash": transition[
            "next_baseline_state_hash"
        ],
        "status": STATUS_AUTHORIZED,
        "authorization_requested": False,
        "authorization_validated": True,
        "authorization_consumed": False,
        "transition_created": True,
        "transition_persisted": False,
        "correction_applied": False,
        "supersession_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "EXACT_TARGET_ONLY",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt proves only that one valid operational "
            "authorization exactly matches one evidence-verified claim-"
            "correction transition candidate. It creates the existing "
            "authorized transition record but does not consume the "
            "authorization through persistence, apply the correction, "
            "supersede canonical state, establish truth, or grant general "
            "write or execution authority."
        ),
    }
    return {
        **body,
        "authorization_binding_hash": _hash(body),
    }


def validate_authorized_verified_claim_correction_transition(
    receipt: Mapping[str, Any],
) -> bool:
    """Regenerate the receipt and require exact schema and identity."""

    if type(receipt) is not dict:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "receipt must be a plain dictionary"
        )
    if set(receipt) != AUTHORIZED_BINDING_FIELDS:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "receipt fields do not match the versioned schema"
        )
    if (
        receipt.get("type") != AUTHORIZED_BINDING_TYPE
        or receipt.get("version") != AUTHORIZED_BINDING_VERSION
    ):
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "receipt type or version is invalid"
        )

    try:
        rebuilt = authorize_verified_claim_correction_transition(
            transition_binding=receipt["transition_binding"],
            authorization=receipt["operational_authorization"],
        )
    except (KeyError, TypeError) as exc:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "receipt content is malformed"
        ) from exc

    if rebuilt != receipt:
        raise AuthorizedVerifiedClaimCorrectionTransitionError(
            "receipt does not match its verified correction and authorization"
        )

    return True
