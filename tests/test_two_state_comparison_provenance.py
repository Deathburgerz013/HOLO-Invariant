import pytest

from holosim.canonical import stable_hash
from holosim.invariant_reflection import (
    InvariantReflectionError,
    build_invariant_reflection_receipt,
    verify_invariant_reflection_receipt,
)


def test_two_state_provenance_rejects_fabricated_residual():
    baseline = {"value": 1}
    observed = {"value": 2}

    prior_body = {"type": "test_prior"}
    prior = {
        **prior_body,
        "receipt_hash": stable_hash(prior_body),
    }

    receipt = build_invariant_reflection_receipt(
        reflection_id="two-state-provenance",
        prior_receipt=prior,
        invariant_id="baseline",
        invariant_state=baseline,
        reflected_state=observed,
        evidence_status="VERIFIED",
    )

    assert verify_invariant_reflection_receipt(receipt) is True

    fabricated = dict(receipt)
    fabricated["residual_paths"] = ["invented.path"]

    fabricated["residual_hash"] = stable_hash({
        "invariant_hash": fabricated["invariant_hash"],
        "reflected_state_hash": fabricated["reflected_state_hash"],
        "residual_paths": fabricated["residual_paths"],
    })

    fabricated["receipt_hash"] = stable_hash({
        key: value
        for key, value in fabricated.items()
        if key != "receipt_hash"
    })

    assert verify_invariant_reflection_receipt(fabricated) is True

    with pytest.raises(InvariantReflectionError):
        verify_invariant_reflection_receipt(
            fabricated,
            invariant_state=baseline,
            reflected_state=observed,
        )




def _receipt(invariant, reflected, status="VERIFIED"):
    prior_body = {"type": "test_prior"}
    prior = {**prior_body, "receipt_hash": stable_hash(prior_body)}
    return build_invariant_reflection_receipt(
        reflection_id="boundary-test",
        prior_receipt=prior,
        invariant_id="baseline",
        invariant_state=invariant,
        reflected_state=reflected,
        evidence_status=status,
    )


def test_independent_comparison_accepts_explicit_null_states():
    receipt = _receipt(None, None)

    assert verify_invariant_reflection_receipt(
        receipt,
        invariant_state=None,
        reflected_state=None,
    ) is True


def test_independent_comparison_accepts_matching_states():
    receipt = _receipt({"value": 1}, {"value": 2})

    assert verify_invariant_reflection_receipt(
        receipt,
        invariant_state={"value": 1},
        reflected_state={"value": 2},
    ) is True


@pytest.mark.parametrize("side", ["invariant", "reflected"])
def test_independent_comparison_requires_both_states(side):
    receipt = _receipt({"value": 1}, {"value": 2})

    kwargs = (
        {"invariant_state": {"value": 1}}
        if side == "invariant"
        else {"reflected_state": {"value": 2}}
    )

    with pytest.raises(InvariantReflectionError):
        verify_invariant_reflection_receipt(receipt, **kwargs)


@pytest.mark.parametrize("side", ["invariant", "reflected"])
def test_independent_comparison_rejects_wrong_state_hash(side):
    receipt = _receipt({"value": 1}, {"value": 2})

    kwargs = {
        "invariant_state": {"value": 1},
        "reflected_state": {"value": 2},
    }

    kwargs[f"{side}_state"] = {"value": 999}

    with pytest.raises(InvariantReflectionError):
        verify_invariant_reflection_receipt(receipt, **kwargs)


def test_independent_comparison_rejects_malformed_state():
    receipt = _receipt({"value": 1}, {"value": 2})

    with pytest.raises(InvariantReflectionError):
        verify_invariant_reflection_receipt(
            receipt,
            invariant_state={"value": float("nan")},
            reflected_state={"value": 2},
        )


def test_independent_comparison_accepts_unverified_null_reflection():
    receipt = _receipt({"value": 1}, None, "UNVERIFIED")

    assert verify_invariant_reflection_receipt(
        receipt,
        invariant_state={"value": 1},
        reflected_state=None,
    ) is True


def test_independent_comparison_rejects_unverified_nonnull_reflection():
    receipt = _receipt({"value": 1}, None, "UNVERIFIED")

    with pytest.raises(InvariantReflectionError):
        verify_invariant_reflection_receipt(
            receipt,
            invariant_state={"value": 1},
            reflected_state={"value": 2},
        )
