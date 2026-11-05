"""Direct regression tests for signed continuation reentry verification."""

from __future__ import annotations

import hashlib
import shutil

import pytest

from holosim.signed_continuation_reentry import (
    verify_signed_continuation_reentry,
)
from holosim.signed_origin_checkpoint import sign_origin_checkpoint
from tests.test_continuation_signed_origin_binding import (
    build_pair,
    candidate_for,
    make_key,
)


pytestmark = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None,
    reason="OpenSSH ssh-keygen unavailable",
)


@pytest.fixture
def evidence(tmp_path):
    original, replacement = build_pair()

    candidate = candidate_for(original)
    replacement_candidate = candidate_for(replacement)

    key, policy = make_key(tmp_path, "legitimate")
    attacker_key, attacker_policy = make_key(tmp_path, "attacker")

    def sign(data, signer):
        return sign_origin_checkpoint(
            candidate=data,
            validator_id="idx:v1",
            contributor_id=None,
            signer_identity="anchor",
            private_key_path=signer,
        )

    return {
        "original": original,
        "replacement": replacement,
        "candidate": candidate,
        "replacement_candidate": replacement_candidate,
        "checkpoint": sign(candidate, key),
        "attacker_checkpoint": sign(replacement_candidate, attacker_key),
        "policy": policy,
        "attacker_policy": attacker_policy,
        "pin": hashlib.sha256(policy.read_bytes()).hexdigest(),
    }


def verify(evidence, **changes):
    arguments = {
        "candidate": evidence["candidate"],
        "checkpoint": evidence["checkpoint"],
        "handoff": evidence["original"],
        "entry_id": "E-001",
        "allowed_signers_path": evidence["policy"],
        "expected_policy_sha256": evidence["pin"],
    }
    arguments.update(changes)
    return verify_signed_continuation_reentry(**arguments)


def assert_no_authority(result):
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["policy_custody_verified"] is False


def test_valid_signed_handoff_binding(evidence):
    result = verify(evidence)

    assert result["status"] == "VERIFIED"
    assert result["verified"] is True
    assert_no_authority(result)


def test_coherent_replacement_handoff_rejected(evidence):
    result = verify(evidence, handoff=evidence["replacement"])

    assert result["status"] == "REJECTED_BINDING"
    assert result["verified"] is False
    assert_no_authority(result)


def test_wrong_entry_id_rejected(evidence):
    result = verify(evidence, entry_id="E-999")

    assert result["status"] == "REJECTED_ENTRY"
    assert result["verified"] is False
    assert_no_authority(result)


def test_tampered_candidate_rejected(evidence):
    candidate = evidence["candidate"].replace(
        b"handoff-sha256:",
        b"handoff-sha256:tampered-",
    )

    result = verify(evidence, candidate=candidate)

    assert result["status"] == "REJECTED_ORIGIN"
    assert result["verified"] is False
    assert_no_authority(result)


def test_attacker_policy_rejected_against_original_pin(evidence):
    result = verify(
        evidence,
        candidate=evidence["replacement_candidate"],
        checkpoint=evidence["attacker_checkpoint"],
        handoff=evidence["replacement"],
        allowed_signers_path=evidence["attacker_policy"],
    )

    assert result["status"] == "REJECTED_ORIGIN"
    assert result["verified"] is False
    assert_no_authority(result)


def test_missing_entry_identifier_rejected(evidence):
    result = verify(evidence, entry_id="")

    assert result["status"] == "REJECTED_ENTRY"
    assert result["verified"] is False
    assert_no_authority(result)


def test_invalid_handoff_rejected(evidence):
    invalid = dict(evidence["original"])
    invalid["handoff_hash"] = "0" * 64

    result = verify(evidence, handoff=invalid)

    assert result["status"] == "REJECTED_HANDOFF"
    assert result["verified"] is False
    assert_no_authority(result)


def test_invalid_candidate_type_rejected(evidence):
    result = verify(evidence, candidate="not bytes")

    assert result["status"] == "REJECTED_CANDIDATE"
    assert result["verified"] is False
    assert_no_authority(result)
def test_duplicate_handoff_reference_rejected(evidence):
    candidate = evidence["candidate"]

    original_entry = candidate.split(b"| | ENTRY\n", 1)[1].split(
        b"| | }=============================================================|", 1
    )[0]

    second_entry = original_entry.replace(
        b"ENTRY_ID: E-001",
        b"ENTRY_ID: E-002",
    )

    duplicate = candidate.replace(
        b"| | COLLECTION_STATUS",
        b"| | ENTRY\n" + second_entry
        + b"| | }=============================================================|\n"
        + b"| | COLLECTION_STATUS",
        1,
    )

    from holosim.spine_admission import build_spine_admission_receipt

    admission = build_spine_admission_receipt(
        duplicate.decode("utf-8"),
        validator_id="idx:v1",
    )
    assert admission["decision"] == "ADMITTED"

    key, policy = make_key(
        evidence["policy"].parent,
        "duplicate-reference",
    )

    checkpoint = sign_origin_checkpoint(
        candidate=duplicate,
        validator_id="idx:v1",
        contributor_id=None,
        signer_identity="anchor",
        private_key_path=key,
    )

    result = verify(
        evidence,
        candidate=duplicate,
        checkpoint=checkpoint,
        allowed_signers_path=policy,
        expected_policy_sha256=hashlib.sha256(
            policy.read_bytes()
        ).hexdigest(),
    )

    assert result["status"] == "REJECTED_BINDING"
    assert result["verified"] is False
    assert_no_authority(result)


def test_duplicate_entry_field_rejected(evidence):
    candidate = evidence["candidate"].replace(
        b"| | ENTRY_ID: E-001",
        b"| | ENTRY_ID: E-001\n| | ENTRY_ID: E-001",
        1,
    )

    from holosim.spine_admission import build_spine_admission_receipt

    admission = build_spine_admission_receipt(
        candidate.decode("utf-8"),
        validator_id="idx:v1",
    )

    assert admission["decision"] == "REJECTED"

    result = verify(evidence, candidate=candidate)

    assert result["verified"] is False
    assert_no_authority(result)
