"""Read-only evaluation of guarantee candidates for human review.

Design provenance: the evidence-accumulation gates were adapted conceptually
from ``NovasPlace/CSM`` ``src/belief-promotion.ts`` at commit
``7cd1fd896782fca5240ef171c06c3ed9ce62e1fb``.  No authorship or participation
by that repository's maintainers is implied.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


GUARANTEE_REVIEW_TYPE = "holo_guarantee_review_eligibility"
GUARANTEE_REVIEW_VERSION = 1


class GuaranteeReviewEligibilityError(ValueError):
    """Raised when review eligibility cannot be evaluated honestly."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise GuaranteeReviewEligibilityError(
            "review eligibility could not be canonicalized"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuaranteeReviewEligibilityError(
            f"{field} must be a non-empty string"
        )
    return value


def _require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GuaranteeReviewEligibilityError(
            f"{field} must be a non-negative integer"
        )
    return value


def _require_positive_int(value: Any, field: str) -> int:
    result = _require_nonnegative_int(value, field)
    if result == 0:
        raise GuaranteeReviewEligibilityError(
            f"{field} must be a positive integer"
        )
    return result


def _require_probability(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= float(value) <= 1.0
    ):
        raise GuaranteeReviewEligibilityError(
            f"{field} must be a finite number between 0 and 1"
        )
    return float(value)


def _require_unique_string_list(value: Any, field: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise GuaranteeReviewEligibilityError(
            f"{field} must be a sequence"
        )

    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        checked = _require_nonempty_string(item, f"{field}[{index}]")
        if checked in seen:
            raise GuaranteeReviewEligibilityError(
                f"{field} must contain unique values"
            )
        seen.add(checked)
        result.append(checked)
    return result


def evaluate_guarantee_review_eligibility(
    candidate: Mapping[str, Any],
    *,
    minimum_confidence: float = 0.8,
    minimum_reinforcements: int = 2,
    minimum_evidence_refs: int = 2,
    minimum_sessions: int = 2,
) -> dict[str, Any]:
    """Return a deterministic, non-authoritative review-eligibility receipt."""
    if not isinstance(candidate, Mapping):
        raise GuaranteeReviewEligibilityError("candidate must be a mapping")

    required_fields = {
        "guarantee_id",
        "confidence",
        "reinforcement_count",
        "evidence_refs",
        "session_ids",
        "contradiction_count",
        "dedup_key",
        "duplicate_of",
    }
    if set(candidate) != required_fields:
        raise GuaranteeReviewEligibilityError("candidate fields are invalid")

    guarantee_id = _require_nonempty_string(
        candidate["guarantee_id"], "guarantee_id"
    )
    confidence = _require_probability(candidate["confidence"], "confidence")
    reinforcement_count = _require_nonnegative_int(
        candidate["reinforcement_count"], "reinforcement_count"
    )
    evidence_refs = _require_unique_string_list(
        candidate["evidence_refs"], "evidence_refs"
    )
    session_ids = _require_unique_string_list(
        candidate["session_ids"], "session_ids"
    )
    contradiction_count = _require_nonnegative_int(
        candidate["contradiction_count"], "contradiction_count"
    )
    dedup_key = _require_nonempty_string(candidate["dedup_key"], "dedup_key")

    duplicate_of_value = candidate["duplicate_of"]
    duplicate_of = (
        None
        if duplicate_of_value is None
        else _require_nonempty_string(duplicate_of_value, "duplicate_of")
    )
    if duplicate_of == guarantee_id:
        raise GuaranteeReviewEligibilityError(
            "duplicate_of cannot equal guarantee_id"
        )

    thresholds = {
        "minimum_confidence": _require_probability(
            minimum_confidence, "minimum_confidence"
        ),
        "minimum_reinforcements": _require_positive_int(
            minimum_reinforcements, "minimum_reinforcements"
        ),
        "minimum_evidence_refs": _require_positive_int(
            minimum_evidence_refs, "minimum_evidence_refs"
        ),
        "minimum_sessions": _require_positive_int(
            minimum_sessions, "minimum_sessions"
        ),
    }

    checks = {
        "confidence": confidence >= thresholds["minimum_confidence"],
        "reinforcement": (
            reinforcement_count >= thresholds["minimum_reinforcements"]
        ),
        "evidence": len(evidence_refs) >= thresholds["minimum_evidence_refs"],
        "session_diversity": len(session_ids) >= thresholds["minimum_sessions"],
        "uncontradicted": contradiction_count == 0,
        "unique": duplicate_of is None,
    }

    if duplicate_of is not None:
        decision = "DUPLICATE"
    elif contradiction_count > 0:
        decision = "CONTRADICTED"
    elif not checks["confidence"]:
        decision = "INSUFFICIENT_CONFIDENCE"
    elif not checks["reinforcement"]:
        decision = "INSUFFICIENT_REINFORCEMENT"
    elif not checks["evidence"]:
        decision = "INSUFFICIENT_EVIDENCE"
    elif not checks["session_diversity"]:
        decision = "INSUFFICIENT_SESSION_DIVERSITY"
    else:
        decision = "REVIEW_ELIGIBLE"

    candidate_body = {
        "guarantee_id": guarantee_id,
        "confidence": confidence,
        "reinforcement_count": reinforcement_count,
        "evidence_refs": evidence_refs,
        "session_ids": session_ids,
        "contradiction_count": contradiction_count,
        "dedup_key": dedup_key,
        "duplicate_of": duplicate_of,
    }
    body = {
        "type": GUARANTEE_REVIEW_TYPE,
        "version": GUARANTEE_REVIEW_VERSION,
        "candidate": candidate_body,
        "candidate_hash": _canonical_hash(candidate_body),
        "thresholds": thresholds,
        "checks": checks,
        "decision": decision,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "receipt_hash": _canonical_hash(body)}
