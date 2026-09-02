from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.proof_authority_boundary import (
    ProofAuthorityBoundaryError,
    assess_proof_use,
    build_bounded_proof,
    validate_bounded_proof,
)


def _proof():
    return build_bounded_proof(
        proof_id="proof-suite-main",
        claim_id="claim-suite-passed",
        claim="The declared test suite passed for the examined commit.",
        assumptions=["test runner reports exit status faithfully"],
        method={"command": ["python", "-m", "pytest", "-q"], "return_code": 0},
        scope={"repository": "HOLO-Invariant", "commit": "abc123"},
        evidence_bindings=[{"evidence_id": "pytest-run", "evidence_sha256": "a" * 64}],
        conclusion="The declared suite passed for commit abc123.",
        limitations=["This does not prove unspecified behavior."],
    )


def _assess(proof, **overrides):
    values = {
        "proof": proof,
        "requested_claim_id": "claim-suite-passed",
        "requested_scope": {"repository": "HOLO-Invariant", "commit": "abc123"},
    }
    values.update(overrides)
    return assess_proof_use(**values)


def _assert_no_authority(result):
    assert result["effect_permitted"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["promotion_authority"] == "NONE"
    assert result["trust_root_authority"] == "NONE"


def test_exact_claim_and_scope_support_only_the_bounded_conclusion():
    result = _assess(_proof())
    assert result["decision"] == "BOUNDED_CONCLUSION_SUPPORTED"
    assert result["conclusion_supported"] is True
    _assert_no_authority(result)


@pytest.mark.parametrize(
    "override",
    [
        {"requested_claim_id": "claim-program-is-correct"},
        {"requested_scope": {"repository": "HOLO-Invariant", "commit": "later"}},
    ],
)
def test_proof_does_not_support_a_different_claim_or_scope(override):
    result = _assess(_proof(), **override)
    assert result["decision"] == "OUTSIDE_PROOF_BOUNDARY"
    assert result["conclusion_supported"] is False
    _assert_no_authority(result)


@pytest.mark.parametrize("authority", ["WRITE", "EXECUTE", "PROMOTE", "ALTER_TRUST_ROOT"])
def test_proof_never_grants_operational_authority(authority):
    result = _assess(_proof(), requested_authority=authority)
    assert result["decision"] == "SEPARATE_AUTHORITY_REQUIRED"
    assert result["conclusion_supported"] is False
    _assert_no_authority(result)


def test_proof_hash_is_rejected_when_substituted_for_authorization():
    proof = _proof()
    result = _assess(
        proof,
        requested_authority="WRITE",
        authorization_reference=proof["proof_hash"],
    )
    assert result["decision"] == "REJECTED_PROOF_AS_AUTHORITY"
    assert result["proof_substitution_attempted"] is True
    _assert_no_authority(result)


def test_independent_reference_is_referred_not_accepted():
    result = _assess(
        _proof(),
        requested_authority="EXECUTE",
        authorization_reference="signed-permit:operator:17",
    )
    assert result["decision"] == "REFER_TO_AUTHORITY_GATE"
    assert result["proof_substitution_attempted"] is False
    _assert_no_authority(result)


def test_proof_is_deterministic_under_unordered_inputs():
    first = _proof()
    second = build_bounded_proof(
        proof_id="proof-suite-main",
        claim_id="claim-suite-passed",
        claim="The declared test suite passed for the examined commit.",
        assumptions=["test runner reports exit status faithfully"],
        method={"return_code": 0, "command": ["python", "-m", "pytest", "-q"]},
        scope={"commit": "abc123", "repository": "HOLO-Invariant"},
        evidence_bindings=[{"evidence_sha256": "a" * 64, "evidence_id": "pytest-run"}],
        conclusion="The declared suite passed for commit abc123.",
        limitations=["This does not prove unspecified behavior."],
    )
    assert second == first


def test_rehashed_authority_forgery_is_rejected():
    forged = deepcopy(_proof())
    forged["write_authority"] = "PROOF"
    body = {key: value for key, value in forged.items() if key != "proof_hash"}
    forged["proof_hash"] = stable_hash(body)
    with pytest.raises(ProofAuthorityBoundaryError, match="cannot grant authority"):
        validate_bounded_proof(forged)


def test_undeclared_fields_are_rejected_even_when_rehashed():
    forged = deepcopy(_proof())
    forged["approved"] = True
    body = {key: value for key, value in forged.items() if key != "proof_hash"}
    forged["proof_hash"] = stable_hash(body)
    with pytest.raises(ProofAuthorityBoundaryError, match="fields"):
        validate_bounded_proof(forged)
