"""Read-only continuity binding across bounded investigation artifacts.

This module does not generate interpretations, execute checks, eliminate
interpretations, decide truth, resolve uncertainty, mutate source artifacts,
or grant authority.

It only verifies that supplied investigation artifacts preserve identity and
that any interpretation-set contraction was already authorized by the
InterpretationSetReceipt evidence-binding contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.interpretation_set_receipt import InterpretationSetReceipt


RECEIPT_TYPE = "bounded_investigation_continuity"
RECEIPT_VERSION = 1


class InvestigationContinuityError(ValueError):
    """Raised when supplied investigation artifacts break continuity."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvestigationContinuityError(
            f"{field} must be a non-empty string"
        )
    return value.strip()


def _candidate_ids(
    distinguishability_receipt: Mapping[str, Any],
) -> set[str]:
    matrix = distinguishability_receipt.get("outcome_matrix")

    if not isinstance(matrix, Mapping):
        raise InvestigationContinuityError(
            "distinguishability_receipt.outcome_matrix must be a mapping"
        )

    candidate_ids: set[str] = set()

    for candidate_id in matrix:
        candidate_ids.add(
            _required_text(
                candidate_id,
                "distinguishability_receipt candidate id",
            )
        )

    return candidate_ids


def _validate_distinguishability_authority(
    receipt: Mapping[str, Any],
) -> None:
    if receipt.get("truth_claimed") is not False:
        raise InvestigationContinuityError(
            "distinguishability receipt must not claim truth"
        )

    if receipt.get("accepted") is not False:
        raise InvestigationContinuityError(
            "distinguishability receipt must not claim acceptance"
        )

    if receipt.get("write_authority") != "NONE":
        raise InvestigationContinuityError(
            "distinguishability receipt must have no write authority"
        )


def _next_check_state(
    next_check_receipt: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if next_check_receipt is None:
        return None

    if not isinstance(next_check_receipt, Mapping):
        raise InvestigationContinuityError(
            "next_check_receipt must be a mapping or None"
        )

    if next_check_receipt.get("truth_claimed") is not False:
        raise InvestigationContinuityError(
            "next-check receipt must not claim truth"
        )

    if next_check_receipt.get("accepted") is not False:
        raise InvestigationContinuityError(
            "next-check receipt must not claim acceptance"
        )

    if next_check_receipt.get("write_authority") != "NONE":
        raise InvestigationContinuityError(
            "next-check receipt must have no write authority"
        )

    if next_check_receipt.get("execution_authorized") is not False:
        raise InvestigationContinuityError(
            "next-check receipt must not authorize execution"
        )

    candidate_checks = next_check_receipt.get("candidate_checks", [])

    if (
        isinstance(candidate_checks, (str, bytes))
        or not isinstance(candidate_checks, list)
    ):
        raise InvestigationContinuityError(
            "next_check_receipt.candidate_checks must be a list"
        )

    return {
        "receipt_type": next_check_receipt.get("type"),
        "receipt_id": (
            next_check_receipt.get("routing_id")
            or next_check_receipt.get("organizer_id")
        ),
        "candidate_check_count": len(candidate_checks),
    }


def bind_investigation_continuity(
    *,
    investigation_id: str,
    question: str,
    interpretation_before: InterpretationSetReceipt,
    distinguishability_receipt: Mapping[str, Any],
    interpretation_after: InterpretationSetReceipt,
    next_check_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind already-produced investigation artifacts without adding authority."""

    investigation = _required_text(investigation_id, "investigation_id")
    bounded_question = _required_text(question, "question")

    if not isinstance(interpretation_before, InterpretationSetReceipt):
        raise InvestigationContinuityError(
            "interpretation_before must be an InterpretationSetReceipt"
        )

    if not isinstance(interpretation_after, InterpretationSetReceipt):
        raise InvestigationContinuityError(
            "interpretation_after must be an InterpretationSetReceipt"
        )

    if (
        interpretation_before.observation_id
        != interpretation_after.observation_id
    ):
        raise InvestigationContinuityError(
            "interpretation observation identity changed"
        )

    if not isinstance(distinguishability_receipt, Mapping):
        raise InvestigationContinuityError(
            "distinguishability_receipt must be a mapping"
        )

    _validate_distinguishability_authority(
        distinguishability_receipt
    )

    before = tuple(interpretation_before.current_set)
    after = tuple(interpretation_after.current_set)

    before_set = set(before)
    after_set = set(after)

    if len(before_set) != len(before):
        raise InvestigationContinuityError(
            "interpretation_before contains duplicate identities"
        )

    if len(after_set) != len(after):
        raise InvestigationContinuityError(
            "interpretation_after contains duplicate identities"
        )

    if not after_set.issubset(before_set):
        raise InvestigationContinuityError(
            "interpretation_after introduced a new interpretation"
        )

    distinguishability_candidates = _candidate_ids(
        distinguishability_receipt
    )

    if not distinguishability_candidates.issubset(before_set):
        raise InvestigationContinuityError(
            "distinguishability receipt contains an unknown interpretation"
        )

    removed = tuple(
        candidate for candidate in before if candidate not in after_set
    )

    # Reconstruct what the supplied after-receipt itself authorizes.
    # If a caller merely hands us a contracted prior_set, that is not evidence
    # that the missing members were validly subtracted from the before-set.
    authorized_after = InterpretationSetReceipt(
        observation_id=interpretation_after.observation_id,
        prior_set=before,
        ranks=interpretation_after.ranks,
        subtract_receipts=interpretation_after.subtract_receipts,
        justification_notices=interpretation_after.justification_notices,
        evidence_receipt_hashes=interpretation_after.evidence_receipt_hashes,
    )

    if tuple(authorized_after.current_set) != after:
        raise InvestigationContinuityError(
            "interpretation contraction is not justified by verified subtraction"
        )

    unresolved_pairs = distinguishability_receipt.get(
        "unresolved_pairs", []
    )
    indistinguishable_pairs = distinguishability_receipt.get(
        "indistinguishable_pairs", []
    )

    for field, pairs in (
        ("unresolved_pairs", unresolved_pairs),
        ("indistinguishable_pairs", indistinguishable_pairs),
    ):
        if isinstance(pairs, (str, bytes)) or not isinstance(pairs, list):
            raise InvestigationContinuityError(
                f"distinguishability_receipt.{field} must be a list"
            )

    next_check = _next_check_state(next_check_receipt)

    if len(after) <= 1:
        status = "NO_REMAINING_ALTERNATIVES"
    elif next_check is not None and next_check["candidate_check_count"] > 0:
        status = "CONTINUES"
    else:
        status = "BOUNDED_UNRESOLVED_STOP"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "investigation_id": investigation,
        "question": bounded_question,
        "observation_id": interpretation_before.observation_id,
        "before_interpretations": list(before),
        "after_interpretations": list(after),
        "removed_interpretations": list(removed),
        "distinguishability_receipt_hash": _required_text(
            distinguishability_receipt.get("receipt_hash"),
            "distinguishability_receipt.receipt_hash",
        ),
        "distinguishability_candidates": sorted(
            distinguishability_candidates
        ),
        "unresolved_pairs": unresolved_pairs,
        "indistinguishable_pairs": indistinguishable_pairs,
        "next_check": next_check,
        "status": status,
        "distinguishability_grants_elimination": False,
        "truth_claimed": False,
        "accepted": False,
        "execution_authorized": False,
        "state_change_authorized": False,
        "write_authority": "NONE",
    }

    try:
        receipt_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise InvestigationContinuityError(str(exc)) from exc

    return {**body, "receipt_hash": receipt_hash}