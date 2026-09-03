from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.recall_verification import (
    RecallVerificationError,
    build_recall_verification_receipt,
    verify_recall_verification_receipt,
)


REFERENCE = {"statement": "the anchor preserves identity", "version": 1}


def _inputs():
    return {
        "claim_id": "recall.anchor",
        "reference_id": "spine.anchor",
        "reference_version": "v1",
        "reference_access_status": "AVAILABLE",
        "expected_reference_hash": stable_hash(REFERENCE),
        "reference_value": deepcopy(REFERENCE),
        "candidate_access_status": "AVAILABLE",
        "candidate_value": deepcopy(REFERENCE),
    }


def _receipt():
    return build_recall_verification_receipt(**_inputs())


def test_exact_external_match_is_valid_without_memory_claim() -> None:
    receipt = _receipt()
    assert receipt["recall_status"] == "VALID"
    assert receipt["status_reason"] == "EXACT_HASH_MATCH"
    assert receipt["exact_match"] is True
    assert receipt["memory_claimed"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["authorship_claimed"] is False
    assert receipt["relevance_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_recall_verification_receipt(receipt) is True


def test_mismatch_against_intact_reference_is_invalid() -> None:
    inputs = _inputs()
    inputs["candidate_value"] = {"statement": "different", "version": 1}
    receipt = build_recall_verification_receipt(**inputs)
    assert receipt["recall_status"] == "INVALID"
    assert receipt["status_reason"] == "EXACT_HASH_MISMATCH"
    assert receipt["exact_match"] is False


@pytest.mark.parametrize("status", ["ABSENT", "INACCESSIBLE", "UNCERTAIN"])
def test_unavailable_reference_is_unknown(status) -> None:
    inputs = _inputs()
    inputs["reference_access_status"] = status
    inputs["reference_value"] = None
    receipt = build_recall_verification_receipt(**inputs)
    assert receipt["recall_status"] == "UNKNOWN"
    assert receipt["status_reason"] == f"REFERENCE_{status}"
    assert receipt["exact_match"] is None


def test_corrupt_reference_is_unknown_not_invalid_recall() -> None:
    inputs = _inputs()
    inputs["expected_reference_hash"] = "0" * 64
    receipt = build_recall_verification_receipt(**inputs)
    assert receipt["recall_status"] == "UNKNOWN"
    assert receipt["status_reason"] == "REFERENCE_CORRUPT"


def test_missing_expected_hash_is_unknown() -> None:
    inputs = _inputs()
    inputs["expected_reference_hash"] = None
    receipt = build_recall_verification_receipt(**inputs)
    assert receipt["status_reason"] == "REFERENCE_HASH_UNAVAILABLE"
    assert receipt["recall_status"] == "UNKNOWN"


def test_unavailable_candidate_is_unknown() -> None:
    inputs = _inputs()
    inputs["candidate_access_status"] = "ABSENT"
    inputs["candidate_value"] = None
    receipt = build_recall_verification_receipt(**inputs)
    assert receipt["status_reason"] == "CANDIDATE_ABSENT"
    assert receipt["recall_status"] == "UNKNOWN"


def test_receipt_contains_hashes_not_private_values() -> None:
    receipt = _receipt()
    assert "reference_value" not in receipt
    assert "candidate_value" not in receipt
    assert receipt["observed_reference_hash"] == stable_hash(REFERENCE)
    assert receipt["candidate_hash"] == stable_hash(REFERENCE)


def test_later_input_mutation_cannot_change_receipt() -> None:
    inputs = _inputs()
    receipt = build_recall_verification_receipt(**inputs)
    inputs["reference_value"]["statement"] = "changed"
    inputs["candidate_value"]["statement"] = "changed"
    assert receipt == _receipt()


def test_nonfinite_value_is_rejected() -> None:
    inputs = _inputs()
    inputs["candidate_value"] = {"value": float("nan")}
    with pytest.raises(RecallVerificationError, match="finite"):
        build_recall_verification_receipt(**inputs)


def test_unsupported_encoding_is_rejected() -> None:
    inputs = _inputs()
    inputs["encoding"] = "ambiguous-text"
    with pytest.raises(RecallVerificationError, match="unsupported"):
        build_recall_verification_receipt(**inputs)


def test_value_cannot_hide_behind_unavailable_status() -> None:
    inputs = _inputs()
    inputs["reference_access_status"] = "ABSENT"
    with pytest.raises(RecallVerificationError, match="must be null"):
        build_recall_verification_receipt(**inputs)


def test_hash_tampering_is_rejected() -> None:
    receipt = _receipt()
    receipt["candidate_hash"] = "1" * 64
    with pytest.raises(RecallVerificationError):
        verify_recall_verification_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recall_status", "INVALID"),
        ("exact_match", False),
        ("memory_claimed", True),
        ("accepted", True),
        ("write_authority", "MODEL"),
    ],
)
def test_rehashed_semantic_forgery_is_rejected(field, value) -> None:
    receipt = _receipt()
    receipt[field] = value
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(RecallVerificationError):
        verify_recall_verification_receipt(receipt)


def test_extra_authority_field_is_rejected() -> None:
    receipt = _receipt()
    receipt["approval_authority"] = "MODEL"
    with pytest.raises(RecallVerificationError, match="fields mismatch"):
        verify_recall_verification_receipt(receipt)
