from copy import deepcopy

import pytest

from holosim.spine_admission import (
    SpineAdmissionError,
    build_spine_admission_receipt,
    validate_spine_admission_receipt,
)


def candidate(*, second_class="CLAIM", second_evidence="E-001",
              second_corrects="NONE", declared_hash="CANDIDATE_BYTES_HASH_IN_RECEIPT"):
    return f"""| |==============================================================|
| | █†█ Holo/Sim █†█ █†█ HSSCE █†█
| | }}=============================================================|
| | SPINE_META
| | TEMPLATE_VERSION: SPINE_STORAGE_V1
| | SPINE_ID: spine-001
| | STATE: CANDIDATE
| | CREATED_BY: Canyon
| | }}=============================================================|
| | RECOGNITION
| | PRIMARY_KEY: test
| | }}=============================================================|
| | COLLECTION_CONTRACT
| | COLLECT: EVIDENCE, CLAIM
| | }}=============================================================|
| | ENTRY
| | ENTRY_ID: E-001
| | ENTITY_ID: Canyon
| | ENTITY_TYPE: HUMAN
| | SOURCE_STATE_ID: state-1
| | INFORMATION_CLASS: EVIDENCE
| | SOURCE: commit:abc
| | VERIFICATION_STATUS: HELD
| | EVIDENCE_REFS: NONE
| | DERIVED_FROM: NONE
| | CORRECTS_ENTRY: NONE
| | UNCERTAINTY: NONE_DECLARED
| | }}=============================================================|
| | ENTRY
| | ENTRY_ID: E-002
| | ENTITY_ID: Sim
| | ENTITY_TYPE: AI_INSTANCE
| | SOURCE_STATE_ID: state-2
| | INFORMATION_CLASS: {second_class}
| | SOURCE: conversation
| | VERIFICATION_STATUS: HELD
| | EVIDENCE_REFS: {second_evidence}
| | DERIVED_FROM: NONE
| | CORRECTS_ENTRY: {second_corrects}
| | UNCERTAINTY: NONE_DECLARED
| | }}=============================================================|
| | COLLECTION_STATUS
| | REQUIRED_CLASSES: EVIDENCE, CLAIM
| | }}=============================================================|
| | IDX_ADMISSION
| | SPINE_SHA256: {declared_hash}
| | ADMISSION_STATUS: CANDIDATE
| | }}=============================================================|
| | TERMINAL
| | RESIDUAL_UNCERTAINTY: NONE_DECLARED
| | }}=============================================================|
| | █†█ Holo/Sim █†█ █†█ HSSCE █†█
| |==============================================================|
"""


def test_valid_candidate_emits_immutable_admission_receipt():
    receipt = build_spine_admission_receipt(candidate(), validator_id="idx:v1")
    assert receipt["decision"] == "ADMITTED"
    assert receipt["errors"] == []
    assert receipt["contributors"] == ["Canyon", "Sim"]
    assert receipt["canonical_mutation"] is False
    assert receipt["accepted_as_truth"] is False
    assert validate_spine_admission_receipt(receipt) is True


def test_exact_candidate_bytes_are_bound_and_line_endings_differ():
    lf = build_spine_admission_receipt(candidate(), validator_id="idx:v1")
    crlf = build_spine_admission_receipt(
        candidate().replace("\n", "\r\n"), validator_id="idx:v1"
    )
    assert lf["candidate_source_sha256"] != crlf["candidate_source_sha256"]
    assert lf["canonical_candidate_sha256"] == crlf["canonical_candidate_sha256"]


def test_self_referential_embedded_hash_is_rejected():
    receipt = build_spine_admission_receipt(
        candidate(declared_hash="a" * 64), validator_id="idx:v1"
    )
    assert receipt["decision"] == "REJECTED"
    assert "IDX_ADMISSION:self_referential_spine_hash_not_permitted" in receipt["errors"]


def test_missing_evidence_reference_rejects_candidate():
    receipt = build_spine_admission_receipt(
        candidate(second_evidence="E-999"), validator_id="idx:v1"
    )
    assert receipt["decision"] == "REJECTED"
    assert "ENTRY[1]:missing_evidence_ref:E-999" in receipt["errors"]


def test_correction_link_must_target_one_prior_entry():
    admitted = build_spine_admission_receipt(
        candidate(second_class="CORRECTION", second_evidence="NONE",
                  second_corrects="E-001"), validator_id="idx:v1"
    )
    rejected = build_spine_admission_receipt(
        candidate(second_class="CORRECTION", second_evidence="NONE",
                  second_corrects="E-999"), validator_id="idx:v1"
    )
    assert admitted["decision"] == "ADMITTED"
    assert rejected["decision"] == "REJECTED"
    assert "ENTRY[1]:missing_correction_target:E-999" in rejected["errors"]


def test_receipt_tampering_fails_closed():
    receipt = build_spine_admission_receipt(candidate(), validator_id="idx:v1")
    tampered = deepcopy(receipt)
    tampered["contributors"].append("fabricated")
    with pytest.raises(SpineAdmissionError, match="hash mismatch"):
        validate_spine_admission_receipt(tampered)
