"""Construct exact, evidence-bound claim-correction candidates without applying them."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.baseline_promotion_gate import STATUS_JUSTIFIED_TO_PROPOSE
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.evidence_bound_baseline_observation import (
    EvidenceBoundBaselineError,
    compare_evidence_bound_baseline_observations,
    evaluate_evidence_bound_baseline_promotion,
)

CORRECTION_TYPE = "bounded_claim_correction_proposal"
CORRECTION_VERSION = 1
STATUS_CORRECTION_CANDIDATE_CREATED = "CORRECTION_CANDIDATE_CREATED"
PROPOSED_REPLACEMENTS_FIELD = "proposed_claim_replacements"

CORRECTION_FIELDS = {
    "type",
    "version",
    "comparison",
    "promotion",
    "baseline_id",
    "baseline_state_hash",
    "current_claims",
    "corrected_claim_ids",
    "proposed_replacements",
    "candidate_claims",
    "candidate_baseline_hash",
    "evidence_result_hashes",
    "replacement_evidence",
    "status",
    "candidate_claim_set_created",
    "correction_applied",
    "supersession_performed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "canonical_mutation",
    "interpretation_notice",
    "proposal_hash",
}


class BoundedClaimCorrectionError(ValueError):
    """Raised when an exact claim-correction proposal cannot be justified."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise BoundedClaimCorrectionError(str(exc)) from exc


def _validate_claim_id(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedClaimCorrectionError(
            "claim ids must be nonempty plain strings"
        )
    if value != value.strip():
        raise BoundedClaimCorrectionError(
            "claim ids must not contain outer whitespace"
        )
    return value


def _validate_claim_mapping(
    value: Mapping[str, Any],
    *,
    field: str,
    require_nonempty: bool,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise BoundedClaimCorrectionError(
            f"{field} must be a plain dictionary"
        )
    if require_nonempty and not value:
        raise BoundedClaimCorrectionError(f"{field} must not be empty")

    normalized: dict[str, Any] = {}
    for claim_id, claim in value.items():
        checked_id = _validate_claim_id(claim_id)
        _hash(claim)
        normalized[checked_id] = deepcopy(claim)

    return {
        claim_id: normalized[claim_id]
        for claim_id in sorted(normalized)
    }


def _validate_source_receipts(
    *,
    comparison: Mapping[str, Any],
    promotion: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(comparison) is not dict:
        raise BoundedClaimCorrectionError(
            "comparison must be a plain dictionary"
        )
    if type(promotion) is not dict:
        raise BoundedClaimCorrectionError(
            "promotion must be a plain dictionary"
        )

    try:
        rebuilt_comparison = compare_evidence_bound_baseline_observations(
            comparison["left_binding"],
            comparison["right_binding"],
        )
    except (KeyError, TypeError, EvidenceBoundBaselineError) as exc:
        raise BoundedClaimCorrectionError(
            f"comparison is invalid: {exc}"
        ) from exc

    if rebuilt_comparison != comparison:
        raise BoundedClaimCorrectionError(
            "comparison does not match its evidence bindings"
        )

    try:
        rebuilt_promotion = evaluate_evidence_bound_baseline_promotion(
            comparison=rebuilt_comparison
        )
    except EvidenceBoundBaselineError as exc:
        raise BoundedClaimCorrectionError(
            f"promotion is invalid: {exc}"
        ) from exc

    if rebuilt_promotion != promotion:
        raise BoundedClaimCorrectionError(
            "promotion does not match the supplied comparison"
        )

    if promotion["gate"]["status"] != STATUS_JUSTIFIED_TO_PROPOSE:
        raise BoundedClaimCorrectionError(
            "promotion is not justified to propose"
        )

    return rebuilt_comparison, rebuilt_promotion


def _replacement_evidence(
    *,
    comparison: Mapping[str, Any],
    corrected_claim_ids: list[str],
    proposed_replacements: Mapping[str, Any],
) -> dict[str, list[str]]:
    expected_ids = set(corrected_claim_ids)
    evidence_by_claim = {
        claim_id: []
        for claim_id in corrected_claim_ids
    }

    for side in ("left_binding", "right_binding"):
        binding = comparison[side]
        result = binding["observation_result"]

        if result["status"] != "OBSERVED":
            raise BoundedClaimCorrectionError(
                "claim replacement evidence must be OBSERVED"
            )

        evidence = result["evidence"]
        declarations = evidence.get(PROPOSED_REPLACEMENTS_FIELD)

        if type(declarations) is not dict:
            raise BoundedClaimCorrectionError(
                "each observation result must contain a "
                "proposed_claim_replacements dictionary"
            )

        for claim_id in declarations:
            _validate_claim_id(claim_id)

        if set(declarations) != expected_ids:
            raise BoundedClaimCorrectionError(
                "evidence replacement ids must exactly match corrected claim ids"
            )

        for claim_id in corrected_claim_ids:
            if _hash(declarations[claim_id]) != _hash(
                proposed_replacements[claim_id]
            ):
                raise BoundedClaimCorrectionError(
                    f"observers do not agree on replacement for {claim_id}"
                )
            evidence_by_claim[claim_id].append(result["result_hash"])

    return {
        claim_id: sorted(evidence_by_claim[claim_id])
        for claim_id in corrected_claim_ids
    }


def propose_bounded_claim_correction(
    *,
    comparison: Mapping[str, Any],
    promotion: Mapping[str, Any],
    current_claims: Mapping[str, Any],
    proposed_replacements: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an exact successor candidate without accepting or applying it."""

    checked_comparison, checked_promotion = _validate_source_receipts(
        comparison=comparison,
        promotion=promotion,
    )

    underlying = checked_comparison["comparison"]
    corrected_claim_ids = list(underlying["correction"])

    if underlying["extension"]:
        raise BoundedClaimCorrectionError(
            "comparison contains extensions outside this correction boundary"
        )
    if not corrected_claim_ids:
        raise BoundedClaimCorrectionError(
            "comparison contains no corrected claims"
        )

    checked_current = _validate_claim_mapping(
        current_claims,
        field="current_claims",
        require_nonempty=True,
    )
    checked_replacements = _validate_claim_mapping(
        proposed_replacements,
        field="proposed_replacements",
        require_nonempty=True,
    )

    declared_claim_ids = set(underlying["per_claim"])
    if set(checked_current) != declared_claim_ids:
        raise BoundedClaimCorrectionError(
            "current claim ids must exactly match compared claim ids"
        )

    if _hash(checked_current) != checked_comparison["baseline_state_hash"]:
        raise BoundedClaimCorrectionError(
            "current claims do not match baseline_state_hash"
        )

    if set(checked_replacements) != set(corrected_claim_ids):
        raise BoundedClaimCorrectionError(
            "replacement ids must exactly match corrected claim ids"
        )

    for claim_id in corrected_claim_ids:
        if _hash(checked_current[claim_id]) == _hash(
            checked_replacements[claim_id]
        ):
            raise BoundedClaimCorrectionError(
                f"replacement must change claim {claim_id}"
            )

    replacement_evidence = _replacement_evidence(
        comparison=checked_comparison,
        corrected_claim_ids=corrected_claim_ids,
        proposed_replacements=checked_replacements,
    )

    candidate_claims = deepcopy(checked_current)
    for claim_id in corrected_claim_ids:
        candidate_claims[claim_id] = deepcopy(
            checked_replacements[claim_id]
        )
    candidate_claims = {
        claim_id: candidate_claims[claim_id]
        for claim_id in sorted(candidate_claims)
    }

    body = {
        "type": CORRECTION_TYPE,
        "version": CORRECTION_VERSION,
        "comparison": deepcopy(checked_comparison),
        "promotion": deepcopy(checked_promotion),
        "baseline_id": checked_comparison["baseline_id"],
        "baseline_state_hash": checked_comparison["baseline_state_hash"],
        "current_claims": checked_current,
        "corrected_claim_ids": corrected_claim_ids,
        "proposed_replacements": checked_replacements,
        "candidate_claims": candidate_claims,
        "candidate_baseline_hash": _hash(candidate_claims),
        "evidence_result_hashes": list(
            checked_comparison["evidence_result_hashes"]
        ),
        "replacement_evidence": replacement_evidence,
        "status": STATUS_CORRECTION_CANDIDATE_CREATED,
        "candidate_claim_set_created": True,
        "correction_applied": False,
        "supersession_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt proves structural agreement between validated evidence "
            "envelopes and one exact successor candidate only. It does not establish "
            "that either claim is true, prove observer independence, accept or apply "
            "the correction, supersede the baseline, mutate canonical state, or grant "
            "write or execution authority."
        ),
    }
    return {**body, "proposal_hash": _hash(body)}


def validate_bounded_claim_correction(
    proposal: Mapping[str, Any],
) -> bool:
    """Regenerate a proposal and require exact schema, content, and identity."""

    if type(proposal) is not dict:
        raise BoundedClaimCorrectionError(
            "proposal must be a plain dictionary"
        )
    if set(proposal) != CORRECTION_FIELDS:
        raise BoundedClaimCorrectionError(
            "proposal fields do not match the versioned schema"
        )
    if (
        proposal.get("type") != CORRECTION_TYPE
        or proposal.get("version") != CORRECTION_VERSION
    ):
        raise BoundedClaimCorrectionError(
            "proposal type or version is invalid"
        )

    try:
        rebuilt = propose_bounded_claim_correction(
            comparison=proposal["comparison"],
            promotion=proposal["promotion"],
            current_claims=proposal["current_claims"],
            proposed_replacements=proposal["proposed_replacements"],
        )
    except (KeyError, TypeError) as exc:
        raise BoundedClaimCorrectionError(
            "proposal content is malformed"
        ) from exc

    if rebuilt != proposal:
        raise BoundedClaimCorrectionError(
            "proposal does not match its source evidence"
        )

    return True