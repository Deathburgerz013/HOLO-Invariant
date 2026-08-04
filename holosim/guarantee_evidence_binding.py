"""Bind guarantee review eligibility to authenticated occurrence evidence.

A binding receipt derives candidate counts, confidence, evidence references, and
session diversity from verified signed occurrences. Authentication establishes
only origin and integrity; it does not establish truth or grant authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.guarantee_review_eligibility import (
    evaluate_guarantee_review_eligibility,
)
from holosim.signed_occurrence import (
    SignedOccurrenceError,
    verify_signed_occurrence,
)


GUARANTEE_EVIDENCE_BINDING_TYPE = "bounded_guarantee_evidence_binding"
GUARANTEE_EVIDENCE_BINDING_VERSION = 1
EVIDENCE_PAYLOAD_FIELDS = {
    "guarantee_id",
    "session_id",
    "evidence_reference",
    "stance",
}
VALID_STANCES = {"SUPPORT", "CONTRADICT"}


class GuaranteeEvidenceBindingError(ValueError):
    """Raised when occurrence evidence cannot be bound honestly."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise GuaranteeEvidenceBindingError(str(exc)) from exc


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuaranteeEvidenceBindingError(
            f"{field} must be a non-empty string"
        )
    return value


def _occurrence_sequence(value: Any) -> list[Mapping[str, Any]]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not value
    ):
        raise GuaranteeEvidenceBindingError(
            "occurrences must be a non-empty sequence"
        )
    result: list[Mapping[str, Any]] = []
    for index, occurrence in enumerate(value):
        if not isinstance(occurrence, Mapping):
            raise GuaranteeEvidenceBindingError(
                f"occurrences[{index}] must be an object"
            )
        result.append(occurrence)
    return result


def _payload(
    occurrence: Mapping[str, Any],
    *,
    guarantee_id: str,
    index: int,
) -> dict[str, str]:
    payload = occurrence.get("payload")
    if not isinstance(payload, Mapping) or set(payload) != EVIDENCE_PAYLOAD_FIELDS:
        raise GuaranteeEvidenceBindingError(
            f"occurrences[{index}].payload fields are invalid"
        )

    payload_guarantee = _required_text(
        payload["guarantee_id"],
        f"occurrences[{index}].payload.guarantee_id",
    )
    if payload_guarantee != guarantee_id:
        raise GuaranteeEvidenceBindingError(
            f"occurrences[{index}] is bound to a different guarantee"
        )

    stance = _required_text(
        payload["stance"],
        f"occurrences[{index}].payload.stance",
    )
    if stance not in VALID_STANCES:
        raise GuaranteeEvidenceBindingError(
            f"occurrences[{index}].payload.stance is invalid"
        )

    return {
        "guarantee_id": payload_guarantee,
        "session_id": _required_text(
            payload["session_id"],
            f"occurrences[{index}].payload.session_id",
        ),
        "evidence_reference": _required_text(
            payload["evidence_reference"],
            f"occurrences[{index}].payload.evidence_reference",
        ),
        "stance": stance,
    }


def evaluate_bound_guarantee_evidence(
    *,
    guarantee_id: str,
    occurrences: Sequence[Mapping[str, Any]],
    source_secrets: Mapping[str, bytes],
    duplicate_of: str | None = None,
    minimum_confidence: float = 0.8,
    minimum_reinforcements: int = 2,
    minimum_evidence_refs: int = 2,
    minimum_sessions: int = 2,
) -> dict[str, Any]:
    """Derive and evaluate one guarantee candidate from signed occurrences."""
    identity = _required_text(guarantee_id, "guarantee_id")
    occurrence_items = _occurrence_sequence(occurrences)
    if not isinstance(source_secrets, Mapping):
        raise GuaranteeEvidenceBindingError("source_secrets must be a mapping")

    seen_occurrence_ids: set[str] = set()
    seen_sessions: set[str] = set()
    seen_evidence_refs: set[str] = set()
    payloads: list[dict[str, str]] = []
    verification_hashes: list[str] = []
    occurrence_hashes: list[str] = []
    source_ids: list[str] = []

    for index, occurrence in enumerate(occurrence_items):
        try:
            verification = verify_signed_occurrence(
                occurrence=occurrence,
                source_secrets=source_secrets,
                seen_occurrence_ids=seen_occurrence_ids,
            )
        except SignedOccurrenceError as exc:
            raise GuaranteeEvidenceBindingError(
                f"occurrences[{index}] is invalid: {exc}"
            ) from exc

        if not verification["verified"]:
            raise GuaranteeEvidenceBindingError(
                f"occurrences[{index}] was not verified: "
                f"{verification['status']}"
            )

        payload = _payload(
            occurrence,
            guarantee_id=identity,
            index=index,
        )
        occurrence_id = occurrence["occurrence_id"]
        session_id = payload["session_id"]
        evidence_reference = payload["evidence_reference"]

        if session_id in seen_sessions:
            raise GuaranteeEvidenceBindingError(
                "verified occurrences must have unique session_id values"
            )
        if evidence_reference in seen_evidence_refs:
            raise GuaranteeEvidenceBindingError(
                "verified occurrences must have unique evidence_reference values"
            )

        seen_occurrence_ids.add(occurrence_id)
        seen_sessions.add(session_id)
        seen_evidence_refs.add(evidence_reference)
        payloads.append(payload)
        verification_hashes.append(verification["verification_hash"])
        occurrence_hashes.append(verification["occurrence_sha256"])
        source_ids.append(verification["source_id"])

    reinforcement_count = sum(
        payload["stance"] == "SUPPORT" for payload in payloads
    )
    contradiction_count = sum(
        payload["stance"] == "CONTRADICT" for payload in payloads
    )
    confidence = reinforcement_count / len(payloads)

    candidate = {
        "guarantee_id": identity,
        "confidence": confidence,
        "reinforcement_count": reinforcement_count,
        "evidence_refs": [
            payload["evidence_reference"] for payload in payloads
        ],
        "session_ids": [payload["session_id"] for payload in payloads],
        "contradiction_count": contradiction_count,
        "dedup_key": f"guarantee:{identity}",
        "duplicate_of": duplicate_of,
    }
    review = evaluate_guarantee_review_eligibility(
        candidate,
        minimum_confidence=minimum_confidence,
        minimum_reinforcements=minimum_reinforcements,
        minimum_evidence_refs=minimum_evidence_refs,
        minimum_sessions=minimum_sessions,
    )

    body = {
        "type": GUARANTEE_EVIDENCE_BINDING_TYPE,
        "version": GUARANTEE_EVIDENCE_BINDING_VERSION,
        "guarantee_id": identity,
        "source_ids": source_ids,
        "occurrence_hashes": occurrence_hashes,
        "verification_hashes": verification_hashes,
        "derived_candidate": deepcopy(candidate),
        "review": review,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Verified signatures establish origin and integrity only. "
            "They do not establish truth, acceptance, or authority."
        ),
    }
    return {**body, "binding_hash": _hash(body)}
