import pytest

from holosim.canonical import stable_hash
from holosim.declared_verifier_execution_receipt import (
    DeclaredVerifierExecutionReceiptError,
    execute_declared_verifier,
)


def _inputs():
    check_identity = {
        "type": "check_identity",
        "version": 1,
        "check_id": "check:a",
        "check_type": "environment_snapshot_comparison",
        "subject": {"comparison_id": "comparison:a"},
        "reference_ids": ["snapshot:before", "snapshot:after"],
        "scope": {"context": "test"},
        "evidence_references": ["evidence:a"],
        "rule_references": [],
        "input_state_hash": "state:before",
        "result_bound": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    check_identity["check_identity_hash"] = stable_hash(check_identity)

    verifier_check_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": "declared-binding:a",
        "verifier_id": "environment_snapshot_comparison",
        "check_id": "check:a",
        "check_identity_hash": check_identity["check_identity_hash"],
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    verifier_check_binding["binding_hash"] = stable_hash(
        verifier_check_binding
    )

    return check_identity, verifier_check_binding


def _verifier(received_check_identity):
    return {
        "status": "COMPLETE",
        "comparison_id": received_check_identity["subject"]["comparison_id"],
    }


def test_execution_receipt_binds_actual_verifier_result():
    check_identity, verifier_check_binding = _inputs()

    receipt = execute_declared_verifier(
        verifier_check_binding=verifier_check_binding,
        check_identity=check_identity,
        available_verifiers={
            "environment_snapshot_comparison": _verifier,
        },
    )

    expected_result = {
        "status": "COMPLETE",
        "comparison_id": "comparison:a",
    }

    assert receipt["verifier_id"] == "environment_snapshot_comparison"
    assert receipt["check_id"] == "check:a"
    assert receipt["check_identity_hash"] == (
        check_identity["check_identity_hash"]
    )
    assert receipt["result"] == expected_result
    assert receipt["result_hash"] == stable_hash(expected_result)
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["execution_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"


def test_mismatched_check_id_fails_closed():
    check_identity, verifier_check_binding = _inputs()
    verifier_check_binding["check_id"] = "check:b"
    verifier_check_binding["binding_hash"] = stable_hash(
    {
        key: value
        for key, value in verifier_check_binding.items()
        if key != "binding_hash"
    }
)

    with pytest.raises(
        DeclaredVerifierExecutionReceiptError,
        match="check_id mismatch",
    ):
        execute_declared_verifier(
            verifier_check_binding=verifier_check_binding,
            check_identity=check_identity,
            available_verifiers={
                "environment_snapshot_comparison": _verifier,
            },
        )


def test_mismatched_check_identity_hash_fails_closed():
    check_identity, verifier_check_binding = _inputs()

    verifier_check_binding["check_identity_hash"] = stable_hash(
    {"different": "identity"}
)
    verifier_check_binding["binding_hash"] = stable_hash(
    {
        key: value
        for key, value in verifier_check_binding.items()
        if key != "binding_hash"
    }
)

    with pytest.raises(
        DeclaredVerifierExecutionReceiptError,
        match="check_identity_hash mismatch",
    ):
        execute_declared_verifier(
            verifier_check_binding=verifier_check_binding,
            check_identity=check_identity,
            available_verifiers={
                "environment_snapshot_comparison": _verifier,
            },
        )


def test_unavailable_declared_verifier_fails_closed():
    check_identity, verifier_check_binding = _inputs()

    with pytest.raises(
        DeclaredVerifierExecutionReceiptError,
        match="declared verifier is unavailable",
    ):
        execute_declared_verifier(
            verifier_check_binding=verifier_check_binding,
            check_identity=check_identity,
            available_verifiers={},
        )


def test_non_callable_declared_verifier_fails_closed():
    check_identity, verifier_check_binding = _inputs()

    with pytest.raises(
        DeclaredVerifierExecutionReceiptError,
        match="declared verifier must be callable",
    ):
        execute_declared_verifier(
            verifier_check_binding=verifier_check_binding,
            check_identity=check_identity,
            available_verifiers={
                "environment_snapshot_comparison": "not-callable",
            },
        )


def test_verifier_returning_non_mapping_fails_closed():
    check_identity, verifier_check_binding = _inputs()

    def invalid_verifier(received_check_identity):
        return "not a result"

    with pytest.raises(
        DeclaredVerifierExecutionReceiptError,
        match="verifier must return a non-empty mapping",
    ):
        execute_declared_verifier(
            verifier_check_binding=verifier_check_binding,
            check_identity=check_identity,
            available_verifiers={
                "environment_snapshot_comparison": invalid_verifier,
            },
        )


def test_actual_result_change_changes_receipt_hash():
    check_identity, verifier_check_binding = _inputs()

    first = execute_declared_verifier(
        verifier_check_binding=verifier_check_binding,
        check_identity=check_identity,
        available_verifiers={
            "environment_snapshot_comparison": _verifier,
        },
    )

    def different_verifier(received_check_identity):
        return {
            "status": "DIFFERENT",
            "comparison_id": received_check_identity["subject"]["comparison_id"],
        }

    second = execute_declared_verifier(
        verifier_check_binding=verifier_check_binding,
        check_identity=check_identity,
        available_verifiers={
            "environment_snapshot_comparison": different_verifier,
        },
    )

    assert first["result"] != second["result"]
    assert first["result_hash"] != second["result_hash"]
    assert first["receipt_hash"] != second["receipt_hash"]