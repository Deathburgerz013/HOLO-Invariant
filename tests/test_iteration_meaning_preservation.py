import copy

import pytest

from holosim.iteration_meaning_preservation import (
    IterationMeaningPreservationReceiptError,
    build_iteration_meaning_preservation_receipt,
    verify_iteration_meaning_preservation_receipt,
)


def _build(**overrides):
    arguments = {
        "iteration_id": "iteration-1",
        "stage": "SIMPLIFICATION",
        "source_content": (
            "Iteration evolves concepts; corrections remain attributable."
        ),
        "transformed_content": (
            "Iteration evolves concepts; corrections remain attributable."
        ),
        "declared_signals": [
            "iteration evolves concepts",
            "corrections remain attributable",
        ],
        "preserved_signals": [
            "iteration evolves concepts",
            "corrections remain attributable",
        ],
        "inferred_signals": [],
        "observed_at": "2026-09-06T00:00:00Z",
    }
    arguments.update(overrides)
    return build_iteration_meaning_preservation_receipt(**arguments)


def test_complete_declared_scope_is_preserved_but_not_authorized():
    receipt = _build()

    assert receipt["preservation"] == "PRESERVED"
    assert receipt["meaning_preservation_claimed"] is True
    assert receipt["state_change_authorized"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["canonical_mutation"] is False
    assert verify_iteration_meaning_preservation_receipt(receipt) is True


def test_information_losing_simplification_is_explicit_residual():
    receipt = _build(
        transformed_content="Iteration evolves concepts.",
        preserved_signals=["iteration evolves concepts"],
    )

    semantic = receipt["semantic_signal_loss_receipt"]
    assert receipt["preservation"] == "LOSS_DETECTED"
    assert receipt["meaning_preservation_claimed"] is False
    assert semantic["context_preservation"] == "PARTIAL"
    assert semantic["lost_signals"] == ["corrections remain attributable"]
    assert receipt["state_change_authorized"] is False


def test_no_preserved_declared_signals_is_loss_detected():
    receipt = _build(
        transformed_content="Shortened.",
        preserved_signals=[],
    )

    assert receipt["preservation"] == "LOSS_DETECTED"
    assert (
        receipt["semantic_signal_loss_receipt"]["context_preservation"]
        == "NONE"
    )


def test_no_declared_scope_does_not_claim_preservation():
    receipt = _build(
        declared_signals=[],
        preserved_signals=[],
    )

    assert receipt["preservation"] == "NOT_DECLARED"
    assert receipt["meaning_preservation_claimed"] is False


@pytest.mark.parametrize(
    "stage",
    [
        "EVOLUTION",
        "SIMPLIFICATION",
        "REDUNDANCY_REMOVAL",
        "CLARIFICATION",
        "DECLARATION",
    ],
)
def test_each_iteration_stage_can_be_bound(stage):
    receipt = _build(stage=stage)
    assert receipt["stage"] == stage
    assert verify_iteration_meaning_preservation_receipt(receipt) is True


def test_stage_is_canonicalized_to_uppercase():
    receipt = _build(stage="clarification")
    assert receipt["stage"] == "CLARIFICATION"


def test_unknown_stage_fails_closed():
    with pytest.raises(
        IterationMeaningPreservationReceiptError,
        match="allowed iteration stage",
    ):
        _build(stage="MAGIC")


def test_semantic_receipt_is_hash_bound():
    receipt = _build()
    assert (
        receipt["semantic_signal_loss_receipt_hash"]
        == receipt["semantic_signal_loss_receipt"]["receipt_hash"]
    )


def test_tampered_outer_receipt_fails():
    receipt = _build()
    tampered = copy.deepcopy(receipt)
    tampered["preservation"] = "LOSS_DETECTED"

    with pytest.raises(
        IterationMeaningPreservationReceiptError,
        match="receipt hash mismatch",
    ):
        verify_iteration_meaning_preservation_receipt(tampered)


def test_rehashed_tampered_nested_receipt_still_fails():
    receipt = _build()
    tampered = copy.deepcopy(receipt)
    tampered["semantic_signal_loss_receipt"]["lost_signals"] = [
        "fabricated"
    ]

    # Outer hash is intentionally left stale. This first proves the outer
    # envelope catches mutation before nested semantics are trusted.
    with pytest.raises(
        IterationMeaningPreservationReceiptError,
        match="receipt hash mismatch",
    ):
        verify_iteration_meaning_preservation_receipt(tampered)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("state_change_authorized", True),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("canonical_mutation", True),
    ],
)
def test_authority_boundaries_are_fixed(field, bad_value):
    receipt = _build()
    tampered = copy.deepcopy(receipt)
    tampered[field] = bad_value

    with pytest.raises(
        IterationMeaningPreservationReceiptError,
        match="receipt hash mismatch",
    ):
        verify_iteration_meaning_preservation_receipt(tampered)


def test_inferred_signal_is_not_treated_as_preserved():
    receipt = _build(
        preserved_signals=["iteration evolves concepts"],
        inferred_signals=["new interpretation"],
    )

    semantic = receipt["semantic_signal_loss_receipt"]
    assert semantic["inferred_signals"] == ["new interpretation"]
    assert "new interpretation" not in semantic["preserved_signals"]
    assert receipt["preservation"] == "LOSS_DETECTED"


def test_duplicate_declared_signals_fail_closed():
    with pytest.raises(
        IterationMeaningPreservationReceiptError,
        match="must not contain duplicates",
    ):
        _build(
            declared_signals=[
                "iteration evolves concepts",
                "iteration evolves concepts",
            ]
        )
