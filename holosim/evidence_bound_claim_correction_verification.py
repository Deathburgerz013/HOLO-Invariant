"""Verify an exact claim-correction candidate against evidence-bound conditions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.bounded_claim_correction import (
    BoundedClaimCorrectionError,
    validate_bounded_claim_correction,
)
from holosim.bounded_solution_coverage import compare_solution_coverage
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import (
    HookContractError,
    validate_hook_request,
    validate_hook_result,
)

VERIFICATION_TYPE = "evidence_bound_claim_correction_verification"
VERIFICATION_VERSION = 1
VERIFY_ACTION = "verify-claim-condition"
SATISFIED_FIELD = "condition_satisfied"

STATUS_VERIFIED = "VERIFIED_TO_REQUEST_AUTHORIZATION"
STATUS_UNRESOLVED = "UNRESOLVED"
STATUS_REGRESSION = "REGRESSION_OBSERVED"
STATUS_INSUFFICIENT = "INSUFFICIENT_IMPROVEMENT"

VERIFICATION_FIELDS = {
    "type",
    "version",
    "proposal",
    "proposal_hash",
    "baseline_state_hash",
    "candidate_baseline_hash",
    "corrected_claim_ids",
    "claim_conditions",
    "condition_ids",
    "guard_condition_ids",
    "before_evidence",
    "after_evidence",
    "before_outcomes",
    "after_outcomes",
    "coverage",
    "newly_solved",
    "preserved",
    "regressed",
    "unresolved",
    "blocking_unavailable",
    "unverified_claim_ids",
    "status",
    "verification_complete",
    "verified_to_request_authorization",
    "authorization_requested",
    "transition_created",
    "correction_applied",
    "supersession_performed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "canonical_mutation",
    "interpretation_notice",
    "verification_hash",
}


class EvidenceBoundClaimCorrectionVerificationError(ValueError):
    """Raised when claim-correction verification evidence is malformed."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise EvidenceBoundClaimCorrectionVerificationError(str(exc)) from exc


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise EvidenceBoundClaimCorrectionVerificationError(
            f"{field} must be a nonempty plain string"
        )
    if value != value.strip():
        raise EvidenceBoundClaimCorrectionVerificationError(
            f"{field} must not contain outer whitespace"
        )
    return value


def _validate_proposal(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    if type(proposal) is not dict:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "proposal must be a plain dictionary"
        )
    try:
        validate_bounded_claim_correction(proposal)
    except BoundedClaimCorrectionError as exc:
        raise EvidenceBoundClaimCorrectionVerificationError(
            f"proposal is invalid: {exc}"
        ) from exc
    return deepcopy(proposal)


def _validate_claim_conditions(
    value: Mapping[str, Any],
    *,
    corrected_claim_ids: list[str],
) -> tuple[dict[str, list[str]], set[str]]:
    if type(value) is not dict:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "claim_conditions must be a plain dictionary"
        )
    if set(value) != set(corrected_claim_ids):
        raise EvidenceBoundClaimCorrectionVerificationError(
            "claim_conditions must exactly match corrected claim ids"
        )

    normalized: dict[str, list[str]] = {}
    owned_conditions: set[str] = set()

    for claim_id in sorted(value):
        _identifier(claim_id, "claim_id")
        conditions = value[claim_id]
        if type(conditions) not in {list, tuple} or not conditions:
            raise EvidenceBoundClaimCorrectionVerificationError(
                "each corrected claim must declare one or more conditions"
            )

        checked_conditions: list[str] = []
        local_seen: set[str] = set()
        for condition_id in conditions:
            checked_id = _identifier(condition_id, "condition_id")
            if checked_id in local_seen:
                raise EvidenceBoundClaimCorrectionVerificationError(
                    f"duplicate condition id for claim {claim_id}"
                )
            if checked_id in owned_conditions:
                raise EvidenceBoundClaimCorrectionVerificationError(
                    f"condition {checked_id} is assigned to multiple claims"
                )
            local_seen.add(checked_id)
            owned_conditions.add(checked_id)
            checked_conditions.append(checked_id)

        normalized[claim_id] = sorted(checked_conditions)

    return normalized, owned_conditions


def _validate_evidence_mapping_shape(
    value: Mapping[str, Any],
    *,
    field: str,
) -> list[str]:
    if type(value) is not dict or not value:
        raise EvidenceBoundClaimCorrectionVerificationError(
            f"{field} must be a nonempty plain dictionary"
        )
    if len(value) > 256:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "verification may declare at most 256 conditions"
        )

    condition_ids: list[str] = []
    for condition_id in value:
        condition_ids.append(_identifier(condition_id, "condition_id"))
    return sorted(condition_ids)


def _validate_evidence_set(
    value: Mapping[str, Any],
    *,
    field: str,
    phase: str,
    claim_set_hash: str,
    condition_ids: list[str],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, bool | None],
    list[dict[str, str]],
]:
    if type(value) is not dict:
        raise EvidenceBoundClaimCorrectionVerificationError(
            f"{field} must be a plain dictionary"
        )
    if set(value) != set(condition_ids):
        raise EvidenceBoundClaimCorrectionVerificationError(
            "before and after evidence must contain the same condition ids"
        )

    checked_evidence: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, bool | None] = {}
    blocking: list[dict[str, str]] = []

    for condition_id in condition_ids:
        bundle = value[condition_id]
        if type(bundle) is not dict or set(bundle) != {"request", "result"}:
            raise EvidenceBoundClaimCorrectionVerificationError(
                f"{field}[{condition_id}] must contain request and result"
            )

        request = bundle["request"]
        result = bundle["result"]

        try:
            validate_hook_request(request)
            validate_hook_result(result, request=request)
        except HookContractError as exc:
            raise EvidenceBoundClaimCorrectionVerificationError(
                f"{field}[{condition_id}] is invalid: {exc}"
            ) from exc

        if request["action"] != VERIFY_ACTION:
            raise EvidenceBoundClaimCorrectionVerificationError(
                f"{field}[{condition_id}] uses the wrong action"
            )
        if request["reference"] != condition_id:
            raise EvidenceBoundClaimCorrectionVerificationError(
                f"{field}[{condition_id}] reference does not match condition id"
            )

        expected_payload = {
            "condition_id": condition_id,
            "claim_set_hash": claim_set_hash,
        }
        if request["payload"] != expected_payload:
            raise EvidenceBoundClaimCorrectionVerificationError(
                f"{field}[{condition_id}] is bound to the wrong claim set"
            )

        evidence = result["evidence"]
        if result["status"] == "OBSERVED":
            if set(evidence) != {SATISFIED_FIELD}:
                raise EvidenceBoundClaimCorrectionVerificationError(
                    f"{field}[{condition_id}] observed evidence must contain "
                    "only condition_satisfied"
                )
            outcome = evidence[SATISFIED_FIELD]
            if type(outcome) is not bool:
                raise EvidenceBoundClaimCorrectionVerificationError(
                    "condition_satisfied must be a boolean"
                )
            outcomes[condition_id] = outcome
        else:
            if SATISFIED_FIELD in evidence:
                raise EvidenceBoundClaimCorrectionVerificationError(
                    "failed or unavailable evidence cannot claim satisfaction"
                )
            outcomes[condition_id] = None
            blocking.append(
                {
                    "condition_id": condition_id,
                    "phase": phase,
                    "status": result["status"],
                    "result_hash": result["result_hash"],
                }
            )

        checked_evidence[condition_id] = deepcopy(bundle)

    return checked_evidence, outcomes, blocking


def verify_evidence_bound_claim_correction(
    *,
    proposal: Mapping[str, Any],
    claim_conditions: Mapping[str, Any],
    before_evidence: Mapping[str, Any],
    after_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify bounded improvement without authorizing or applying correction."""

    checked_proposal = _validate_proposal(proposal)
    corrected_claim_ids = list(checked_proposal["corrected_claim_ids"])

    checked_claim_conditions, owned_conditions = _validate_claim_conditions(
        claim_conditions,
        corrected_claim_ids=corrected_claim_ids,
    )

    before_ids = _validate_evidence_mapping_shape(
        before_evidence,
        field="before_evidence",
    )
    after_ids = _validate_evidence_mapping_shape(
        after_evidence,
        field="after_evidence",
    )
    if before_ids != after_ids:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "before and after evidence must contain the same condition ids"
        )
    if not owned_conditions.issubset(set(before_ids)):
        raise EvidenceBoundClaimCorrectionVerificationError(
            "every claim condition must have before and after evidence"
        )

    checked_before, before_outcomes, before_blocking = _validate_evidence_set(
        before_evidence,
        field="before_evidence",
        phase="BEFORE",
        claim_set_hash=checked_proposal["baseline_state_hash"],
        condition_ids=before_ids,
    )
    checked_after, after_outcomes, after_blocking = _validate_evidence_set(
        after_evidence,
        field="after_evidence",
        phase="AFTER",
        claim_set_hash=checked_proposal["candidate_baseline_hash"],
        condition_ids=before_ids,
    )

    for condition_id in before_ids:
        before_hash = checked_before[condition_id]["result"]["result_hash"]
        after_hash = checked_after[condition_id]["result"]["result_hash"]
        if before_hash == after_hash:
            raise EvidenceBoundClaimCorrectionVerificationError(
                f"condition {condition_id} reuses one result across claim sets"
            )

    observed_condition_ids = [
        condition_id
        for condition_id in before_ids
        if before_outcomes[condition_id] is not None
        and after_outcomes[condition_id] is not None
    ]
    observed_before = {
        condition_id: before_outcomes[condition_id]
        for condition_id in observed_condition_ids
    }
    observed_after = {
        condition_id: after_outcomes[condition_id]
        for condition_id in observed_condition_ids
    }

    coverage = compare_solution_coverage(
        before=observed_before,
        after=observed_after,
    )

    blocking_unavailable = sorted(
        before_blocking + after_blocking,
        key=lambda item: (
            item["condition_id"],
            item["phase"],
            item["status"],
            item["result_hash"],
        ),
    )
    unavailable_condition_ids = {
        item["condition_id"]
        for item in blocking_unavailable
    }
    unresolved = sorted(
        set(coverage["unresolved"]) | unavailable_condition_ids
    )

    newly_solved = list(coverage["newly_solved"])
    preserved = list(coverage["preserved"])
    regressed = list(coverage["regressed"])

    newly_solved_set = set(newly_solved)
    unverified_claim_ids = [
        claim_id
        for claim_id in corrected_claim_ids
        if not (
            set(checked_claim_conditions[claim_id])
            & newly_solved_set
        )
    ]

    verification_complete = (
        bool(before_ids)
        and not blocking_unavailable
        and not unresolved
        and not regressed
        and not unverified_claim_ids
        and len(observed_condition_ids) == len(before_ids)
        and coverage["closure_ready"] is True
    )

    if blocking_unavailable:
        status = STATUS_UNRESOLVED
    elif regressed:
        status = STATUS_REGRESSION
    elif unresolved or unverified_claim_ids:
        status = STATUS_INSUFFICIENT
    else:
        status = STATUS_VERIFIED

    verified_to_request_authorization = (
        status == STATUS_VERIFIED
        and verification_complete
    )

    body = {
        "type": VERIFICATION_TYPE,
        "version": VERIFICATION_VERSION,
        "proposal": checked_proposal,
        "proposal_hash": checked_proposal["proposal_hash"],
        "baseline_state_hash": checked_proposal["baseline_state_hash"],
        "candidate_baseline_hash": checked_proposal[
            "candidate_baseline_hash"
        ],
        "corrected_claim_ids": corrected_claim_ids,
        "claim_conditions": checked_claim_conditions,
        "condition_ids": before_ids,
        "guard_condition_ids": sorted(
            set(before_ids) - owned_conditions
        ),
        "before_evidence": checked_before,
        "after_evidence": checked_after,
        "before_outcomes": before_outcomes,
        "after_outcomes": after_outcomes,
        "coverage": coverage,
        "newly_solved": newly_solved,
        "preserved": preserved,
        "regressed": regressed,
        "unresolved": unresolved,
        "blocking_unavailable": blocking_unavailable,
        "unverified_claim_ids": unverified_claim_ids,
        "status": status,
        "verification_complete": verification_complete,
        "verified_to_request_authorization": (
            verified_to_request_authorization
        ),
        "authorization_requested": False,
        "transition_created": False,
        "correction_applied": False,
        "supersession_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt proves only that exact evidence-bound condition "
            "observations show bounded improvement from one validated claim "
            "set to its exact correction candidate. It does not establish "
            "truth, evidence quality, observer independence, authorization, "
            "acceptance, application, persistence, supersession, or authority."
        ),
    }
    return {**body, "verification_hash": _hash(body)}


def validate_evidence_bound_claim_correction_verification(
    verification: Mapping[str, Any],
) -> bool:
    """Regenerate a verification receipt and require exact identity."""

    if type(verification) is not dict:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "verification must be a plain dictionary"
        )
    if set(verification) != VERIFICATION_FIELDS:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "verification fields do not match the versioned schema"
        )
    if (
        verification.get("type") != VERIFICATION_TYPE
        or verification.get("version") != VERIFICATION_VERSION
    ):
        raise EvidenceBoundClaimCorrectionVerificationError(
            "verification type or version is invalid"
        )

    try:
        rebuilt = verify_evidence_bound_claim_correction(
            proposal=verification["proposal"],
            claim_conditions=verification["claim_conditions"],
            before_evidence=verification["before_evidence"],
            after_evidence=verification["after_evidence"],
        )
    except (KeyError, TypeError) as exc:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "verification content is malformed"
        ) from exc

    if rebuilt != verification:
        raise EvidenceBoundClaimCorrectionVerificationError(
            "verification does not match its source evidence"
        )

    return True