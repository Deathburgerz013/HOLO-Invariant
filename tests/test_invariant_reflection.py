from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.functional_awareness_loop import build_functional_awareness_receipt
from holosim.invariant_reflection import (
    InvariantReflectionError,
    build_invariant_reflection_receipt,
    verify_invariant_reflection_receipt,
)


SOLUTION = {
    "solution_id": "solution.adjust",
    "description": "Apply the bounded adjustment.",
    "execution_status": "VERIFIED_EXECUTED",
    "execution_receipt_hash": "a" * 64,
}
ADAPTATION = {
    "adaptation_id": "adaptation.keep",
    "statement": "Propose this adjustment for a later authorized decision.",
}


def prior_receipt():
    return build_functional_awareness_receipt(
        loop_id="loop-1",
        goal_state={"safe": True},
        before_state={"safe": False},
        after_state={"safe": True},
        before_evidence_status="VERIFIED",
        after_evidence_status="VERIFIED",
        solution=SOLUTION,
        adaptation=ADAPTATION,
    )


def build(reflected, *, status="VERIFIED", invariant=None):
    return build_invariant_reflection_receipt(
        reflection_id="reflection-1",
        prior_receipt=prior_receipt(),
        invariant_id="invariant.safe",
        invariant_state={"safe": True} if invariant is None else invariant,
        reflected_state=reflected,
        evidence_status=status,
    )


def rehash(receipt):
    body = {k: v for k, v in receipt.items() if k != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)


def test_exact_reflection_is_invariant_and_requires_no_state_change():
    receipt = build({"safe": True})
    assert receipt["reflection_status"] == "INVARIANT"
    assert receipt["residual_paths"] == []
    assert receipt["residual_hash"] is None
    assert receipt["state_change_required"] is False
    assert verify_invariant_reflection_receipt(receipt)


def test_verified_difference_becomes_explicit_residual():
    receipt = build({"safe": False})
    assert receipt["reflection_status"] == "RESIDUAL"
    assert receipt["residual_paths"] == ["safe"]
    assert receipt["residual_hash"] is not None
    assert receipt["state_change_required"] is True
    assert verify_invariant_reflection_receipt(receipt)


def test_nested_residual_paths_are_deterministic():
    receipt = build(
        {"safe": True, "nested": {"value": 0}},
        invariant={"safe": True, "nested": {"value": 2}},
    )
    assert receipt["residual_paths"] == ["nested.value"]


def test_prior_verified_receipt_identity_is_preserved():
    prior = prior_receipt()
    receipt = build_invariant_reflection_receipt(
        reflection_id="reflection-1",
        prior_receipt=prior,
        invariant_id="invariant.safe",
        invariant_state={"safe": True},
        reflected_state={"safe": True},
        evidence_status="VERIFIED",
    )
    assert receipt["prior_receipt_hash"] == prior["receipt_hash"]


def test_tampered_prior_receipt_is_rejected():
    prior = prior_receipt()
    prior["effect"] = "UNKNOWN"
    with pytest.raises(InvariantReflectionError, match="prior_receipt hash mismatch"):
        build_invariant_reflection_receipt(
            reflection_id="reflection-1",
            prior_receipt=prior,
            invariant_id="invariant.safe",
            invariant_state={"safe": True},
            reflected_state={"safe": True},
            evidence_status="VERIFIED",
        )


@pytest.mark.parametrize("status", ["UNVERIFIED", "UNAVAILABLE"])
def test_unverified_reflection_is_unknown_and_cannot_require_change(status):
    receipt = build(None, status=status)
    assert receipt["reflection_status"] == "UNKNOWN"
    assert receipt["reflected_state_hash"] is None
    assert receipt["residual_paths"] is None
    assert receipt["residual_hash"] is None
    assert receipt["state_change_required"] is False


def test_unverified_reflection_must_not_supply_state():
    with pytest.raises(InvariantReflectionError, match="must be null"):
        build({"safe": False}, status="UNVERIFIED")


def test_raw_states_are_not_copied_into_receipt():
    receipt = build({"safe": False})
    assert "invariant_state" not in receipt
    assert "reflected_state" not in receipt
    assert "prior_receipt" not in receipt


def test_inputs_are_isolated_by_canonical_hashes():
    invariant = {"safe": True, "nested": [1, 2]}
    reflected = deepcopy(invariant)
    receipt = build_invariant_reflection_receipt(
        reflection_id="reflection-1",
        prior_receipt=prior_receipt(),
        invariant_id="invariant.safe",
        invariant_state=invariant,
        reflected_state=reflected,
        evidence_status="VERIFIED",
    )
    invariant["nested"][0] = 99
    reflected["nested"][1] = 99
    assert receipt["reflection_status"] == "INVARIANT"
    assert verify_invariant_reflection_receipt(receipt)


def test_nonfinite_state_is_rejected():
    with pytest.raises(InvariantReflectionError, match="finite"):
        build({"safe": True, "score": float("nan")})


def test_receipt_never_claims_consciousness_truth_acceptance_or_authority():
    receipt = build({"safe": False})
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_receipt_hash_tamper_is_rejected():
    receipt = build({"safe": False})
    receipt["reflection_status"] = "INVARIANT"
    with pytest.raises(InvariantReflectionError, match="receipt hash mismatch"):
        verify_invariant_reflection_receipt(receipt)


def test_rehashed_residual_identity_forgery_is_rejected():
    receipt = build({"safe": False})
    receipt["residual_hash"] = "b" * 64
    rehash(receipt)
    with pytest.raises(InvariantReflectionError, match="residual identity mismatch"):
        verify_invariant_reflection_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subjective_consciousness_claimed", True),
        ("truth_claimed", True),
        ("accepted", True),
        ("write_authority", "SELF"),
        ("execution_authority", "SELF"),
        ("interpretation_notice", "Consciousness proven."),
    ],
)
def test_rehashed_forbidden_claim_or_authority_is_rejected(field, value):
    receipt = build({"safe": False})
    receipt[field] = value
    rehash(receipt)
    with pytest.raises(InvariantReflectionError, match="forbidden claim or authority"):
        verify_invariant_reflection_receipt(receipt)


def test_extra_field_is_rejected_even_if_rehashed():
    receipt = build({"safe": False})
    receipt["future_prediction"] = True
    rehash(receipt)
    with pytest.raises(InvariantReflectionError, match="fields mismatch"):
        verify_invariant_reflection_receipt(receipt)
