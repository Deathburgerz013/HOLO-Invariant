from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.guarantee_evidence_binding import (
    GuaranteeEvidenceBindingError,
    evaluate_bound_guarantee_evidence,
)
from holosim.signed_occurrence import build_signed_occurrence


SECRET_A = b"a" * 32
SECRET_B = b"b" * 32
SECRETS = {
    "source:a": SECRET_A,
    "source:b": SECRET_B,
}


def _occurrence(
    *,
    number: int,
    source_id: str,
    secret: bytes,
    session_id: str,
    evidence_reference: str,
    stance: str = "SUPPORT",
    guarantee_id: str = "attention-cycle-value",
) -> dict[str, object]:
    return build_signed_occurrence(
        source_id=source_id,
        occurrence_id=f"occurrence:{number}",
        payload={
            "guarantee_id": guarantee_id,
            "session_id": session_id,
            "evidence_reference": evidence_reference,
            "stance": stance,
        },
        observed_at=f"2026-08-04T12:00:{number:02d}Z",
        sequence=number,
        nonce=f"nonce:{number:016d}",
        secret=secret,
    )


def _supporting_occurrences() -> list[dict[str, object]]:
    return [
        _occurrence(
            number=1,
            source_id="source:a",
            secret=SECRET_A,
            session_id="session:a",
            evidence_reference="receipt:a",
        ),
        _occurrence(
            number=2,
            source_id="source:b",
            secret=SECRET_B,
            session_id="session:b",
            evidence_reference="receipt:b",
        ),
    ]


def test_verified_occurrences_derive_review_eligible_candidate() -> None:
    result = evaluate_bound_guarantee_evidence(
        guarantee_id="attention-cycle-value",
        occurrences=_supporting_occurrences(),
        source_secrets=SECRETS,
    )

    assert result["derived_candidate"] == {
        "guarantee_id": "attention-cycle-value",
        "confidence": 1.0,
        "reinforcement_count": 2,
        "evidence_refs": ["receipt:a", "receipt:b"],
        "session_ids": ["session:a", "session:b"],
        "contradiction_count": 0,
        "dedup_key": "guarantee:attention-cycle-value",
        "duplicate_of": None,
    }
    assert result["review"]["decision"] == "REVIEW_ELIGIBLE"
    assert len(result["verification_hashes"]) == 2
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_tampered_occurrence_cannot_supply_fabricated_reference() -> None:
    occurrences = _supporting_occurrences()
    occurrences[1]["payload"]["evidence_reference"] = "fabricated"

    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="was not verified: REJECTED_TAMPERED",
    ):
        evaluate_bound_guarantee_evidence(
            guarantee_id="attention-cycle-value",
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_unknown_source_cannot_supply_evidence() -> None:
    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="was not verified: REJECTED_UNKNOWN_SOURCE",
    ):
        evaluate_bound_guarantee_evidence(
            guarantee_id="attention-cycle-value",
            occurrences=_supporting_occurrences(),
            source_secrets={"source:a": SECRET_A},
        )


def test_occurrence_for_another_guarantee_is_rejected() -> None:
    occurrences = _supporting_occurrences()
    occurrences[1] = _occurrence(
        number=2,
        source_id="source:b",
        secret=SECRET_B,
        session_id="session:b",
        evidence_reference="receipt:b",
        guarantee_id="different-guarantee",
    )

    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="bound to a different guarantee",
    ):
        evaluate_bound_guarantee_evidence(
            guarantee_id="attention-cycle-value",
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_duplicate_sessions_cannot_inflate_diversity() -> None:
    occurrences = _supporting_occurrences()
    occurrences[1] = _occurrence(
        number=2,
        source_id="source:b",
        secret=SECRET_B,
        session_id="session:a",
        evidence_reference="receipt:b",
    )

    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="unique session_id values",
    ):
        evaluate_bound_guarantee_evidence(
            guarantee_id="attention-cycle-value",
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_duplicate_evidence_references_cannot_inflate_evidence() -> None:
    occurrences = _supporting_occurrences()
    occurrences[1] = _occurrence(
        number=2,
        source_id="source:b",
        secret=SECRET_B,
        session_id="session:b",
        evidence_reference="receipt:a",
    )

    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="unique evidence_reference values",
    ):
        evaluate_bound_guarantee_evidence(
            guarantee_id="attention-cycle-value",
            occurrences=occurrences,
            source_secrets=SECRETS,
        )


def test_signed_contradiction_blocks_review_eligibility() -> None:
    occurrences = _supporting_occurrences()
    occurrences[1] = _occurrence(
        number=2,
        source_id="source:b",
        secret=SECRET_B,
        session_id="session:b",
        evidence_reference="receipt:b",
        stance="CONTRADICT",
    )

    result = evaluate_bound_guarantee_evidence(
        guarantee_id="attention-cycle-value",
        occurrences=occurrences,
        source_secrets=SECRETS,
    )

    assert result["derived_candidate"]["reinforcement_count"] == 1
    assert result["derived_candidate"]["contradiction_count"] == 1
    assert result["derived_candidate"]["confidence"] == 0.5
    assert result["review"]["decision"] == "CONTRADICTED"


def test_empty_occurrence_set_is_rejected() -> None:
    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="occurrences must be a non-empty sequence",
    ):
        evaluate_bound_guarantee_evidence(
            guarantee_id="attention-cycle-value",
            occurrences=[],
            source_secrets=SECRETS,
        )


def test_inputs_are_not_mutated_and_binding_is_deterministic() -> None:
    occurrences = _supporting_occurrences()
    original = deepcopy(occurrences)

    first = evaluate_bound_guarantee_evidence(
        guarantee_id="attention-cycle-value",
        occurrences=occurrences,
        source_secrets=SECRETS,
    )
    second = evaluate_bound_guarantee_evidence(
        guarantee_id="attention-cycle-value",
        occurrences=occurrences,
        source_secrets=SECRETS,
    )

    assert occurrences == original
    assert first == second
    assert len(first["binding_hash"]) == 64
