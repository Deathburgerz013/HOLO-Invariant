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


def _rehash(state: dict[str, Any]) -> None:
    import hashlib
    import json

    state["truth_hash"] = hashlib.sha256(json.dumps(
        {k: v for k, v in state.items() if k != "truth_hash"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def test_valid_fact_identity_does_not_support_unrelated_statement() -> None:
    from holosim.fact_identity import (
        build_verified_fact_identity_receipt, verify_fact_identity_receipt,
    )

    receipt = build_verified_fact_identity_receipt(
        fact_id="observation-1",
        members=[{"analysis_id": "analysis-1", "finding_id": "finding-1"}],
    )
    before = deepcopy(receipt)
    state = crystallize_truth(
        "Every possible input has been tested successfully.",
        [receipt], verify_fact_identity_receipt,
    )
    validate_truth_state(state)
    assert receipt == before
    assert state["version"] == 2
    assert state["claim_support"] == "NOT_ASSESSED"
    assert state["truth_claimed"] is False
    assert state["execution_authority"] == "NONE"
    assert "do not establish relevance, sufficiency, or statement truth" in state["interpretation_notice"]


@pytest.mark.parametrize("statement", ["Original claim.", "Unrelated new claim."])
def test_revision_never_upgrades_claim_support(statement: str) -> None:
    first = _receipt("r1", "value=10")
    initial = crystallize_truth("Original claim.", [first], _validate_receipt)
    before = deepcopy(initial)
    revised = revise_truth(initial, statement, [first, _receipt("r2", "value=14")], _validate_receipt)
    validate_truth_state(revised)
    assert initial == before
    assert revised["parent_truth_hash"] == initial["truth_hash"]
    assert revised["claim_support"] == "NOT_ASSESSED"
    assert revised["truth_claimed"] is False


@pytest.mark.parametrize("field,value", [
    ("truth_claimed", True), ("truth_claimed", 0),
    ("claim_support", "SUPPORTED"), ("execution_authority", "EXECUTE"),
    ("interpretation_notice", "The statement is justified by verified evidence."),
    ("accepted", True), ("write_authority", "WRITE"),
    ("version", True),
])
def test_rehashed_support_or_authority_claims_rejected(field: str, value: Any) -> None:
    state = crystallize_truth("Claim.", [_receipt("r1", "value=10")], _validate_receipt)
    state[field] = value
    _rehash(state)
    with pytest.raises(TruthStateError):
        validate_truth_state(state)


def test_structural_validation_is_not_claim_or_evidence_replay() -> None:
    state = crystallize_truth("Claim.", [_receipt("r1", "value=10")], _validate_receipt)
    state["statement"] = "Substituted unsupported statement."
    state["evidence_receipts"][0]["verified"] = False
    import hashlib
    import json
    state["evidence_hashes"] = [hashlib.sha256(json.dumps(
        state["evidence_receipts"][0], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()]
    _rehash(state)
    validate_truth_state(state)
    assert state["claim_support"] == "NOT_ASSESSED"
    assert state["truth_claimed"] is False
    with pytest.raises(TruthStateError, match="invalid"):
        crystallize_truth(state["statement"], state["evidence_receipts"], _validate_receipt)


def test_legacy_parent_remains_readable_and_unchanged_on_revision() -> None:
    first = _receipt("r1", "value=10")
    legacy = crystallize_truth("Claim.", [first], _validate_receipt)
    legacy["version"] = 1
    for field in ("truth_claimed", "claim_support", "execution_authority"):
        del legacy[field]
    legacy["interpretation_notice"] = (
        "This state records a statement currently justified by verified "
        "evidence. It does not grant acceptance or write authority. The "
        "statement may move only through a later evidence-bound revision."
    )
    _rehash(legacy)
    before = deepcopy(legacy)
    validate_truth_state(legacy)
    revised = revise_truth(legacy, "Claim.", [first, _receipt("r2", "value=10")], _validate_receipt)
    assert legacy == before
    assert revised["parent_truth_hash"] == legacy["truth_hash"]
    assert revised["version"] == 2
    assert revised["claim_support"] == "NOT_ASSESSED"
    validate_truth_state(revised)
