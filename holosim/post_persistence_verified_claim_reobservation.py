"""Re-observe one persisted verified claim correction without mutation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .bounded_solution_coverage import compare_solution_coverage
from .canonical import CanonicalValueError, stable_hash
from .evidence_bound_claim_correction_verification import (
    STATUS_VERIFIED,
    EvidenceBoundClaimCorrectionVerificationError,
    verify_evidence_bound_claim_correction,
)
from .persistent_baseline_transition import (
    PersistentBaselineTransitionError,
    PersistentBaselineTransitionStore,
    validate_persisted_verified_claim_correction_read,
)


REOBSERVATION_TYPE = "post_persistence_verified_claim_reobservation"
REOBSERVATION_VERSION = 1
STATUS_CONFIRMED = "REOBSERVATION_CONFIRMED"
STATUS_CHANGE = "CHANGE_OBSERVED"
STATUS_UNRESOLVED = "REOBSERVATION_UNRESOLVED"

REOBSERVATION_FIELDS = {
    "type",
    "version",
    "persistence_read",
    "persistence_read_hash",
    "record_id",
    "chain_entry_hash",
    "authorization_binding_hash",
    "original_verification_hash",
    "fresh_verification",
    "fresh_verification_hash",
    "condition_ids",
    "observed_condition_ids",
    "unresolved_condition_ids",
    "changed_condition_ids",
    "outcome_comparison",
    "exact_outcome_match",
    "verified_correction_still_supported",
    "reobservation_complete",
    "status",
    "persistence_still_current",
    "authorization_consumed",
    "transition_persisted",
    "persisted_supersession_observed",
    "persisted_canonical_mutation_observed",
    "correction_applied",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "canonical_mutation",
    "interpretation_notice",
    "reobservation_hash",
}


class PostPersistenceVerifiedClaimReobservationError(ValueError):
    """A persisted correction cannot be safely re-observed."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise PostPersistenceVerifiedClaimReobservationError(str(exc)) from exc


def _validate_store(
    store: PersistentBaselineTransitionStore,
) -> PersistentBaselineTransitionStore:
    if not isinstance(store, PersistentBaselineTransitionStore):
        raise PostPersistenceVerifiedClaimReobservationError(
            "store must be a PersistentBaselineTransitionStore"
        )
    return store


def reobserve_persisted_verified_claim_correction(
    *,
    store: PersistentBaselineTransitionStore,
    record_id: str,
    fresh_after_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-run exact correction conditions against the current persisted head."""
    checked_store = _validate_store(store)
    try:
        persistence_read = checked_store.read_verified_claim_correction(
            record_id=record_id
        )
        validate_persisted_verified_claim_correction_read(persistence_read)
    except PersistentBaselineTransitionError as exc:
        raise PostPersistenceVerifiedClaimReobservationError(
            f"persisted correction cannot be read: {exc}"
        ) from exc

    if persistence_read["record_is_current_head"] is not True:
        raise PostPersistenceVerifiedClaimReobservationError(
            "persisted correction is no longer the current baseline head"
        )

    authorized_correction = persistence_read["record"][
        "authorized_correction"
    ]
    original_verification = authorized_correction["transition_binding"][
        "verification"
    ]
    try:
        fresh_verification = verify_evidence_bound_claim_correction(
            proposal=original_verification["proposal"],
            claim_conditions=original_verification["claim_conditions"],
            before_evidence=original_verification["before_evidence"],
            after_evidence=fresh_after_evidence,
        )
    except EvidenceBoundClaimCorrectionVerificationError as exc:
        raise PostPersistenceVerifiedClaimReobservationError(
            f"fresh re-observation evidence is invalid: {exc}"
        ) from exc

    condition_ids = list(original_verification["condition_ids"])
    for condition_id in condition_ids:
        old_result_hash = original_verification["after_evidence"][condition_id][
            "result"
        ]["result_hash"]
        fresh_result_hash = fresh_verification["after_evidence"][condition_id][
            "result"
        ]["result_hash"]
        if fresh_result_hash == old_result_hash:
            raise PostPersistenceVerifiedClaimReobservationError(
                f"condition {condition_id} reuses persisted after evidence"
            )

    original_outcomes = original_verification["after_outcomes"]
    fresh_outcomes = fresh_verification["after_outcomes"]
    observed_condition_ids = [
        condition_id
        for condition_id in condition_ids
        if fresh_outcomes[condition_id] is not None
    ]
    unresolved_condition_ids = sorted(
        set(condition_ids) - set(observed_condition_ids)
    )
    changed_condition_ids = [
        condition_id
        for condition_id in observed_condition_ids
        if fresh_outcomes[condition_id] != original_outcomes[condition_id]
    ]
    outcome_comparison = compare_solution_coverage(
        before={
            condition_id: original_outcomes[condition_id]
            for condition_id in observed_condition_ids
        },
        after={
            condition_id: fresh_outcomes[condition_id]
            for condition_id in observed_condition_ids
        },
    )

    reobservation_complete = (
        not unresolved_condition_ids
        and len(observed_condition_ids) == len(condition_ids)
    )
    exact_outcome_match = (
        reobservation_complete and not changed_condition_ids
    )
    verified_correction_still_supported = (
        fresh_verification["status"] == STATUS_VERIFIED
        and fresh_verification["verification_complete"] is True
        and fresh_verification["verified_to_request_authorization"] is True
    )

    if unresolved_condition_ids:
        status = STATUS_UNRESOLVED
    elif changed_condition_ids:
        status = STATUS_CHANGE
    else:
        status = STATUS_CONFIRMED

    body = {
        "type": REOBSERVATION_TYPE,
        "version": REOBSERVATION_VERSION,
        "persistence_read": persistence_read,
        "persistence_read_hash": persistence_read["read_hash"],
        "record_id": persistence_read["record_id"],
        "chain_entry_hash": persistence_read["chain_entry_hash"],
        "authorization_binding_hash": authorized_correction[
            "authorization_binding_hash"
        ],
        "original_verification_hash": original_verification[
            "verification_hash"
        ],
        "fresh_verification": fresh_verification,
        "fresh_verification_hash": fresh_verification["verification_hash"],
        "condition_ids": condition_ids,
        "observed_condition_ids": observed_condition_ids,
        "unresolved_condition_ids": unresolved_condition_ids,
        "changed_condition_ids": changed_condition_ids,
        "outcome_comparison": outcome_comparison,
        "exact_outcome_match": exact_outcome_match,
        "verified_correction_still_supported": (
            verified_correction_still_supported
        ),
        "reobservation_complete": reobservation_complete,
        "status": status,
        "persistence_still_current": True,
        "authorization_consumed": True,
        "transition_persisted": True,
        "persisted_supersession_observed": True,
        "persisted_canonical_mutation_observed": True,
        "correction_applied": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt compares fresh condition observations with one "
            "verified correction that is still the current persisted "
            "baseline head. It observes an earlier append-only mutation but "
            "does not mutate state, apply claim text to an external system, "
            "establish truth or acceptance, renew or grant authority, or "
            "authorize another transition."
        ),
    }
    return {**body, "reobservation_hash": _hash(body)}


def validate_post_persistence_verified_claim_reobservation(
    receipt: Mapping[str, Any],
    *,
    store: PersistentBaselineTransitionStore,
) -> bool:
    """Regenerate one current-head re-observation and require exact identity."""
    if type(receipt) is not dict:
        raise PostPersistenceVerifiedClaimReobservationError(
            "receipt must be a plain dictionary"
        )
    if set(receipt) != REOBSERVATION_FIELDS:
        raise PostPersistenceVerifiedClaimReobservationError(
            "receipt fields do not match the versioned schema"
        )
    if (
        receipt.get("type") != REOBSERVATION_TYPE
        or receipt.get("version") != REOBSERVATION_VERSION
    ):
        raise PostPersistenceVerifiedClaimReobservationError(
            "receipt type or version is invalid"
        )

    try:
        rebuilt = reobserve_persisted_verified_claim_correction(
            store=store,
            record_id=receipt["record_id"],
            fresh_after_evidence=receipt["fresh_verification"][
                "after_evidence"
            ],
        )
    except (KeyError, TypeError) as exc:
        raise PostPersistenceVerifiedClaimReobservationError(
            "receipt content is malformed"
        ) from exc

    if rebuilt != receipt:
        raise PostPersistenceVerifiedClaimReobservationError(
            "receipt does not match current persisted evidence re-observation"
        )
    return True
