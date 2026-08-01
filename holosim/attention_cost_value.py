"""Bounded cost and value decisions for attention allocation."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


ATTENTION_DECISION_TYPE = "holo_attention_decision"
ATTENTION_DECISION_VERSION = 1


class AttentionCostValueError(ValueError):
    """Raised when an attention decision cannot be evaluated honestly."""


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
        raise AttentionCostValueError(
            "attention decision could not be canonicalized"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AttentionCostValueError(f"{field} must be a non-empty string")
    return value


def _require_finite_number(value: Any, field: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AttentionCostValueError(f"{field} must be a finite number")

    if not math.isfinite(value):
        raise AttentionCostValueError(f"{field} must be a finite number")

    return value


def evaluate_attention_candidate(
    *,
    candidate_id: str,
    value: float,
    cost: float,
    urgency: float,
    dependency_impact: float,
) -> dict[str, Any]:
    """Evaluate whether a candidate earns bounded processing cycles."""
    normalized_candidate_id = _require_nonempty_string(
        candidate_id,
        "candidate_id",
    )
    normalized_value = _require_finite_number(value, "value")
    normalized_cost = _require_finite_number(cost, "cost")
    normalized_urgency = _require_finite_number(urgency, "urgency")
    normalized_dependency_impact = _require_finite_number(
        dependency_impact,
        "dependency_impact",
    )

    score = (
        normalized_value
        + normalized_urgency
        + normalized_dependency_impact
        - normalized_cost
    )

    decision = "EARN_CYCLES" if score > 0 else "DEFER"

    body = {
        "type": ATTENTION_DECISION_TYPE,
        "version": ATTENTION_DECISION_VERSION,
        "candidate_id": normalized_candidate_id,
        "value": normalized_value,
        "cost": normalized_cost,
        "urgency": normalized_urgency,
        "dependency_impact": normalized_dependency_impact,
        "score": score,
        "decision": decision,
        "accepted": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "decision_hash": _canonical_hash(body),
    }