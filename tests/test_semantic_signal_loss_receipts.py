from copy import deepcopy

import pytest

from holosim.semantic_signal_loss_receipts import (
    SemanticSignalLossReceiptError,
    build_semantic_signal_loss_receipt,
    verify_semantic_signal_loss_receipt,
)


def build_receipt(**overrides):
    arguments = {
        "transformation_id": "speech-to-text-001",
        "source_content": "I never said she stole it.",
        "observed_content": "I never said she stole it.",
        "declared_signals": [
            "intonation",
            "timing",
            "emphasis",
        ],
        "preserved_signals": [
            "timing",
        ],
        "inferred_signals": [],
        "observed_at": "2026-08-19T20:30:00Z",
    }
    arguments.update(overrides)
    return build_semantic_signal_loss_receipt(
        **arguments
    )


def test_matching_text_with_lost_intonation_does_not_claim_same_meaning():
    receipt = build_receipt()

    assert receipt["content_identity"] == "MATCH"
    assert receipt["context_preservation"] == "PARTIAL"
    assert receipt["preserved_signals"] == [
        "timing",
    ]
    assert receipt["lost_signals"] == [
        "emphasis",
        "intonation",
    ]
    assert receipt["interpretation_identity"] == "UNKNOWN"

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["canonical_mutation"] is False
    assert verify_semantic_signal_loss_receipt(
        receipt
    ) is True


def test_complete_declared_signal_preservation_remains_bounded():
    receipt = build_receipt(
        preserved_signals=[
            "intonation",
            "timing",
            "emphasis",
        ],
    )

    assert receipt["content_identity"] == "MATCH"
    assert receipt["context_preservation"] == (
        "COMPLETE_DECLARED_SCOPE"
    )
    assert receipt["lost_signals"] == []
    assert receipt["interpretation_identity"] == "UNKNOWN"
    assert receipt["truth_claimed"] is False


def test_different_content_is_detected_without_interpreting_semantics():
    receipt = build_receipt(
        observed_content="She stole it.",
    )

    assert receipt["content_identity"] == "DIFFERENT"
    assert receipt["interpretation_identity"] == "UNKNOWN"
    assert receipt["source_content_hash"] != receipt[
        "observed_content_hash"
    ]


def test_no_declared_context_is_not_reported_as_complete():
    receipt = build_receipt(
        declared_signals=[],
        preserved_signals=[],
    )

    assert receipt["context_preservation"] == (
        "NOT_DECLARED"
    )
    assert receipt["lost_signals"] == []
    assert receipt["interpretation_identity"] == "UNKNOWN"


def test_inferred_signals_are_separate_from_preserved_signals():
    receipt = build_receipt(
        inferred_signals=[
            "speaker_emotion",
            "sarcasm",
        ],
    )

    assert receipt["inferred_signals"] == [
        "sarcasm",
        "speaker_emotion",
    ]
    assert not set(receipt["inferred_signals"]) & set(
        receipt["preserved_signals"]
    )
    assert receipt["interpretation_identity"] == "UNKNOWN"


def test_signal_lists_are_deterministic():
    first = build_receipt(
        declared_signals=[
            "timing",
            "intonation",
            "emphasis",
        ],
        preserved_signals=[
            "timing",
        ],
    )
    second = build_receipt(
        declared_signals=[
            "emphasis",
            "timing",
            "intonation",
        ],
        preserved_signals=[
            "timing",
        ],
    )

    assert first == second
    assert first["receipt_hash"] == second[
        "receipt_hash"
    ]


def test_preserved_signal_must_be_declared():
    with pytest.raises(
        SemanticSignalLossReceiptError,
        match="preserved signals must be declared",
    ):
        build_receipt(
            preserved_signals=[
                "timing",
                "facial_expression",
            ],
        )


def test_inferred_signal_cannot_also_be_preserved():
    with pytest.raises(
        SemanticSignalLossReceiptError,
        match="inferred signals cannot be preserved",
    ):
        build_receipt(
            inferred_signals=[
                "timing",
            ],
        )


def test_raw_content_is_not_retained_in_receipt():
    receipt = build_receipt()

    assert "source_content" not in receipt
    assert "observed_content" not in receipt
    assert "I never said she stole it." not in str(
        receipt
    )


def test_tampered_receipt_is_rejected():
    receipt = build_receipt()
    tampered = deepcopy(receipt)
    tampered["interpretation_identity"] = "MATCH"

    with pytest.raises(
        SemanticSignalLossReceiptError,
        match="receipt hash mismatch",
    ):
        verify_semantic_signal_loss_receipt(
            tampered
        )