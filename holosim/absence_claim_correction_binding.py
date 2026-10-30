"""Read-only identity binding between observer absence and claim correction."""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.continuity_under_absence import (
    ContinuityUnderAbsenceError,
    reconstruct_continuity,
)
from holosim.verified_claim_correction_transition import (
    VerifiedClaimCorrectionTransitionError,
    validate_verified_claim_correction_transition_candidate,
)

BINDING_TYPE = "absence_claim_correction_binding"
BINDING_VERSION = 1


class AbsenceClaimCorrectionBindingError(ValueError):
    """Continuity and correction identities cannot be validly bound."""


def build_absence_claim_correction_binding(
    *,
    continuity_receipt: Mapping[str, Any],
    external_evidence: Mapping[str, Any],
    transition_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind validated endpoints to one verified correction candidate.

    This establishes state identity only. It does not establish events during
    observer absence, authenticate observers, authorize correction, or mutate state.
    """
    for name, value in (
        ("continuity_receipt", continuity_receipt),
        ("external_evidence", external_evidence),
        ("transition_candidate", transition_candidate),
    ):
        if type(value) is not dict:
            raise AbsenceClaimCorrectionBindingError(
                f"{name} must be a plain dictionary"
            )

    verification = transition_candidate.get("verification")
    if type(verification) is not dict:
        raise AbsenceClaimCorrectionBindingError(
            "transition_candidate.verification must be a plain dictionary"
        )

    proposal = verification.get("proposal")
    if type(proposal) is not dict:
        raise AbsenceClaimCorrectionBindingError(
            "transition_candidate.verification.proposal must be a plain dictionary"
        )

    required = (
        (proposal, "current_claims", "verification.proposal"),
        (proposal, "candidate_claims", "verification.proposal"),
        (transition_candidate, "previous_baseline_state_hash", "transition_candidate"),
        (transition_candidate, "next_baseline_state_hash", "transition_candidate"),
        (transition_candidate, "binding_hash", "transition_candidate"),
        (continuity_receipt, "receipt_hash", "continuity_receipt"),
        (external_evidence, "receipt_hash", "external_evidence"),
    )
    for mapping, field, location in required:
        if field not in mapping:
            raise AbsenceClaimCorrectionBindingError(
                f"missing required field: {location}.{field}"
            )

    try:
        reconstruction = reconstruct_continuity(
            continuity_receipt,
            external_evidence=external_evidence,
            collection_closed=True,
        )
        validate_verified_claim_correction_transition_candidate(
            transition_candidate
        )
    except (
        ContinuityUnderAbsenceError,
        VerifiedClaimCorrectionTransitionError,
        CanonicalValueError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise AbsenceClaimCorrectionBindingError(
            f"source verification failed: {exc}"
        ) from exc

    if (
        reconstruction["prior_state"] != proposal["current_claims"]
        or reconstruction["current_state"] != proposal["candidate_claims"]
        or reconstruction["prior_state_hash"]
        != transition_candidate["previous_baseline_state_hash"]
        or reconstruction["current_state_hash"]
        != transition_candidate["next_baseline_state_hash"]
    ):
        raise AbsenceClaimCorrectionBindingError(
            "continuity endpoints do not match correction state identities"
        )

    body = {
        "type": BINDING_TYPE,
        "version": BINDING_VERSION,
        "continuity_receipt_hash": continuity_receipt["receipt_hash"],
        "external_evidence_hash": external_evidence["receipt_hash"],
        "transition_binding_hash": transition_candidate["binding_hash"],
        "prior_state_hash": reconstruction["prior_state_hash"],
        "current_state_hash": reconstruction["current_state_hash"],
        "absence_interval_observed": False,
        "absence_interval_reconstructed": False,
        "continuity_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    try:
        return {**body, "binding_hash": stable_hash(body)}
    except CanonicalValueError as exc:
        raise AbsenceClaimCorrectionBindingError(str(exc)) from exc


def validate_absence_claim_correction_binding(
    binding: Mapping[str, Any],
    *,
    continuity_receipt: Mapping[str, Any],
    external_evidence: Mapping[str, Any],
    transition_candidate: Mapping[str, Any],
) -> bool:
    """Rebuild the binding from its original evidence and compare exactly."""
    if type(binding) is not dict:
        raise AbsenceClaimCorrectionBindingError(
            "binding must be a plain dictionary"
        )

    expected = build_absence_claim_correction_binding(
        continuity_receipt=continuity_receipt,
        external_evidence=external_evidence,
        transition_candidate=transition_candidate,
    )
    if binding != expected:
        raise AbsenceClaimCorrectionBindingError(
            "binding schema or identity mismatch"
        )
    return True
