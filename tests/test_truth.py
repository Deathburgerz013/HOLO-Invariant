from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import pytest

from holosim.truth import (
    TruthStateError,
    crystallize_truth,
    revise_truth,
    validate_truth_state,
)


def _receipt(receipt_id: str, observation: str) -> dict[str, Any]:
    return {
        "type": "test_evidence_receipt",
        "version": 1,
        "receipt_id": receipt_id,
        "observation": observation,
        "verified": True,
    }


def _validate_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("type") != "test_evidence_receipt":
        raise ValueError("invalid evidence type")

    if receipt.get("version") != 1:
        raise ValueError("invalid evidence version")

    if receipt.get("verified") is not True:
        raise ValueError("evidence is not verified")

    if not isinstance(receipt.get("receipt_id"), str):
        raise ValueError("receipt_id is invalid")

    if not isinstance(receipt.get("observation"), str):
        raise ValueError("observation is invalid")


def test_crystallize_truth_from_verified_evidence() -> None:
    state = crystallize_truth(
        "The observed value is stable.",
        [_receipt("r1", "value=10")],
        _validate_receipt,
    )

    validate_truth_state(state)

    assert state["statement"] == "The observed value is stable."
    assert state["transition"] == "crystallized"
    assert state["parent_truth_hash"] is None
    assert len(state["evidence_receipts"]) == 1
    assert len(state["evidence_hashes"]) == 1
    assert state["accepted"] is False
    assert state["write_authority"] == "NONE"


def test_revise_truth_crystallizes_when_statement_survives() -> None:
    initial = crystallize_truth(
        "The observed value is stable.",
        [_receipt("r1", "value=10")],
        _validate_receipt,
    )

    revised = revise_truth(
        initial,
        "The observed value is stable.",
        [
            _receipt("r1", "value=10"),
            _receipt("r2", "value=10"),
        ],
        _validate_receipt,
    )

    validate_truth_state(revised)

    assert revised["transition"] == "crystallized"
    assert revised["statement"] == initial["statement"]
    assert revised["parent_truth_hash"] == initial["truth_hash"]
    assert len(revised["evidence_receipts"]) == 2


def test_revise_truth_moves_when_statement_changes() -> None:
    initial = crystallize_truth(
        "The observed value is stable.",
        [_receipt("r1", "value=10")],
        _validate_receipt,
    )

    revised = revise_truth(
        initial,
        "The observed value changes under load.",
        [
            _receipt("r1", "value=10"),
            _receipt("r2", "value=14 under load"),
        ],
        _validate_receipt,
    )

    validate_truth_state(revised)

    assert revised["transition"] == "moved"
    assert revised["statement"] == "The observed value changes under load."
    assert revised["parent_truth_hash"] == initial["truth_hash"]


def test_revision_requires_new_verified_evidence() -> None:
    receipt = _receipt("r1", "value=10")
    initial = crystallize_truth(
        "The observed value is stable.",
        [receipt],
        _validate_receipt,
    )

    with pytest.raises(
        TruthStateError,
        match="at least one new verified evidence",
    ):
        revise_truth(
            initial,
            "The observed value is stable.",
            [receipt],
            _validate_receipt,
        )


def test_revision_cannot_remove_prior_evidence() -> None:
    initial = crystallize_truth(
        "The observed value is stable.",
        [
            _receipt("r1", "value=10"),
            _receipt("r2", "value=10"),
        ],
        _validate_receipt,
    )

    with pytest.raises(
        TruthStateError,
        match="cannot remove previously recorded evidence",
    ):
        revise_truth(
            initial,
            "The observed value changed.",
            [
                _receipt("r2", "value=10"),
                _receipt("r3", "value=14"),
            ],
            _validate_receipt,
        )


def test_invalid_evidence_is_rejected() -> None:
    invalid = _receipt("r1", "value=10")
    invalid["verified"] = False

    with pytest.raises(
        TruthStateError,
        match="evidence receipt at index 0 is invalid",
    ):
        crystallize_truth(
            "The observed value is stable.",
            [invalid],
            _validate_receipt,
        )


def test_duplicate_evidence_is_rejected() -> None:
    receipt = _receipt("r1", "value=10")

    with pytest.raises(
        TruthStateError,
        match="duplicate evidence receipt",
    ):
        crystallize_truth(
            "The observed value is stable.",
            [receipt, deepcopy(receipt)],
            _validate_receipt,
        )


def test_tampered_truth_state_is_rejected() -> None:
    state = crystallize_truth(
        "The observed value is stable.",
        [_receipt("r1", "value=10")],
        _validate_receipt,
    )
    state["statement"] = "Tampered statement."

    with pytest.raises(
        TruthStateError,
        match="truth hash is invalid",
    ):
        validate_truth_state(state)


def test_initial_truth_cannot_claim_moved_transition() -> None:
    state = crystallize_truth(
        "The observed value is stable.",
        [_receipt("r1", "value=10")],
        _validate_receipt,
    )

    state["transition"] = "moved"

    body = {
        key: value
        for key, value in state.items()
        if key != "truth_hash"
    }

    import hashlib
    import json

    state["truth_hash"] = hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    with pytest.raises(
        TruthStateError,
        match="initial truth state must be crystallized",
    ):
        validate_truth_state(state)