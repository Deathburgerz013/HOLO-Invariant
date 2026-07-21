from __future__ import annotations

import pytest

from holosim.check_identity import (
    CheckIdentityError,
    bind_check_result,
    build_check_identity,
)


def _identity() -> dict:
    return build_check_identity(
        check_id="check-store-reproduction",
        check_type="FUNCTION_REPRODUCTION",
        subject={"function_id": "STORE"},
        reference_ids=["environment:stored-program-computer"],
        scope={"layer": "memory-write", "bounded": True},
        evidence_references=["fixture:store_reproduction.json"],
        rule_references=["rule:functional-equivalence-by-reproduction"],
        input_state_hash="state-before-check",
    )


def test_build_check_identity_is_deterministic() -> None:
    first = _identity()
    second = _identity()

    assert first == second
    assert first["type"] == "check_identity"
    assert first["check_id"] == "check-store-reproduction"
    assert first["check_type"] == "FUNCTION_REPRODUCTION"
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"


def test_check_identity_hash_changes_when_subject_changes() -> None:
    first = _identity()
    second = build_check_identity(
        check_id="check-store-reproduction",
        check_type="FUNCTION_REPRODUCTION",
        subject={"function_id": "LOAD"},
        reference_ids=["environment:stored-program-computer"],
        scope={"layer": "memory-write", "bounded": True},
        evidence_references=["fixture:store_reproduction.json"],
        rule_references=["rule:functional-equivalence-by-reproduction"],
        input_state_hash="state-before-check",
    )

    assert first["check_identity_hash"] != second["check_identity_hash"]


def test_check_identity_rejects_missing_subject() -> None:
    with pytest.raises(CheckIdentityError, match="subject"):
        build_check_identity(
            check_id="check-1",
            check_type="TEST",
            subject={},
            reference_ids=["ref"],
            scope={"bounded": True},
            evidence_references=["evidence"],
            rule_references=["rule"],
            input_state_hash="state",
        )


def test_check_identity_rejects_missing_scope() -> None:
    with pytest.raises(CheckIdentityError, match="scope"):
        build_check_identity(
            check_id="check-1",
            check_type="TEST",
            subject={"id": "subject"},
            reference_ids=["ref"],
            scope={},
            evidence_references=["evidence"],
            rule_references=["rule"],
            input_state_hash="state",
        )


def test_check_identity_rejects_duplicate_references() -> None:
    with pytest.raises(CheckIdentityError, match="duplicate reference_id"):
        build_check_identity(
            check_id="check-1",
            check_type="TEST",
            subject={"id": "subject"},
            reference_ids=["ref", "ref"],
            scope={"bounded": True},
            evidence_references=["evidence"],
            rule_references=["rule"],
            input_state_hash="state",
        )


def test_bind_check_result_binds_exact_identity() -> None:
    identity = _identity()

    binding = bind_check_result(
        check_identity=identity,
        result={"status": "REPRODUCED"},
        output_state_hash="state-after-check",
        justifier_reference="judgment:store-reproduction",
    )

    assert binding["check_id"] == identity["check_id"]
    assert binding["check_identity_hash"] == identity["check_identity_hash"]
    assert binding["input_state_hash"] == "state-before-check"
    assert binding["output_state_hash"] == "state-after-check"
    assert binding["justifier_reference"] == "judgment:store-reproduction"
    assert binding["accepted"] is False
    assert binding["write_authority"] == "NONE"


def test_bind_check_result_hash_changes_with_result() -> None:
    identity = _identity()
    reproduced = bind_check_result(
        check_identity=identity,
        result={"status": "REPRODUCED"},
        output_state_hash="state-after-check",
    )
    failed = bind_check_result(
        check_identity=identity,
        result={"status": "NOT_REPRODUCED"},
        output_state_hash="state-after-check",
    )

    assert reproduced["binding_hash"] != failed["binding_hash"]
    assert reproduced["result_hash"] != failed["result_hash"]


def test_bind_check_result_rejects_tampered_identity() -> None:
    identity = _identity()
    identity["subject"] = {"function_id": "LOAD"}

    with pytest.raises(CheckIdentityError, match="hash does not match"):
        bind_check_result(
            check_identity=identity,
            result={"status": "REPRODUCED"},
            output_state_hash="state-after-check",
        )


def test_bind_check_result_requires_result() -> None:
    with pytest.raises(CheckIdentityError, match="result"):
        bind_check_result(
            check_identity=_identity(),
            result={},
            output_state_hash="state-after-check",
        )


def test_check_identity_preserves_empty_optional_reference_lists() -> None:
    identity = build_check_identity(
        check_id="check-observation-only",
        check_type="OBSERVATION",
        subject={"id": "environment"},
        reference_ids=[],
        scope={"bounded": True},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state-0",
    )

    assert identity["reference_ids"] == []
    assert identity["evidence_references"] == []
    assert identity["rule_references"] == []
    assert identity["result_bound"] is False


def test_result_binding_does_not_claim_justification_or_acceptance() -> None:
    binding = bind_check_result(
        check_identity=_identity(),
        result={"status": "CONSISTENT"},
        output_state_hash="state-after-check",
    )

    assert "justified" not in binding
    assert binding["justifier_reference"] is None
    assert binding["accepted"] is False
    assert binding["write_authority"] == "NONE"
