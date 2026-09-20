"""Bind a verified directional check outcome into evidence-analysis input.

This adapter preserves an already-derived directional outcome as evidence for
bounded analysis. It does not reinterpret the outcome, establish truth, accept
results, or grant selection, write, or execution authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


class DirectionalEvidenceBindingError(ValueError):
    """Raised when a directional outcome cannot be bound honestly."""


def _verify_directional_outcome(
    directional_outcome: Mapping[str, Any],
) -> str:
    if not isinstance(directional_outcome, Mapping):
        raise DirectionalEvidenceBindingError(
            "directional_outcome must be a mapping"
        )

    if (
        directional_outcome.get("type")
        != "verified_directional_check_outcome"
    ):
        raise DirectionalEvidenceBindingError(
            "directional outcome type mismatch"
        )

    supplied_hash = directional_outcome.get("outcome_hash")
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise DirectionalEvidenceBindingError(
            "directional outcome requires outcome_hash"
        )

    body = {
        key: value
        for key, value in directional_outcome.items()
        if key != "outcome_hash"
    }

    try:
        expected_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise DirectionalEvidenceBindingError(str(exc)) from exc

    if supplied_hash != expected_hash:
        raise DirectionalEvidenceBindingError(
            "directional outcome hash mismatch"
        )

    outcome = directional_outcome.get("outcome")
    if outcome not in {"SUPPORTS", "CONTRADICTS", "UNKNOWN"}:
        raise DirectionalEvidenceBindingError(
            "directional outcome is invalid"
        )

    return supplied_hash


def bind_directional_outcome_to_evidence(
    directional_outcome: Mapping[str, Any],
) -> dict[str, Any]:
    """Preserve one verified directional outcome as analyst evidence."""

    outcome_hash = _verify_directional_outcome(
        directional_outcome
    )

    check_id = directional_outcome.get("check_id")
    if not isinstance(check_id, str) or not check_id:
        raise DirectionalEvidenceBindingError(
            "directional outcome requires check_id"
        )

    outcome = directional_outcome["outcome"]

    return {
        "type": "directional_evidence_binding",
        "version": 1,
        "source_outcome_hash": outcome_hash,
        "source_execution_receipt_hash": directional_outcome[
            "execution_receipt_hash"
        ],
        "source_result_binding_hash": directional_outcome[
            "result_binding_hash"
        ],
        "source_evaluation_rule_hash": directional_outcome[
            "evaluation_rule_hash"
        ],
        "evidence": {
            "evidence_id": check_id,
            "content_sha256": outcome_hash,
            "source_reference": f"directional:{outcome_hash}",
            "availability": "VERIFIED",
        },
        "assessment": {
            "evidence_id": check_id,
            "disposition": "INCLUDED",
            "relation": outcome,
            "rationale": (
                "relation preserved from verified directional "
                "check outcome"
            ),
        },
        "truth_claimed": False,
        "accepted": False,
        "selection_authority": "NONE",
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
