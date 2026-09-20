import pytest

from holosim.canonical import stable_hash
from holosim.check_identity import build_check_identity, bind_check_result
from holosim.declared_verifier_execution_receipt import (
    execute_declared_verifier,
)
from holosim.verified_directional_check_outcome import (
    VerifiedDirectionalCheckOutcomeError,
    build_verified_directional_check_outcome,
)


def _artifacts(result=None):
    if result is None:
        result = {"status": "COMPLETE"}

    check_identity = build_check_identity(
        check_id="check:a",
        check_type="environment_snapshot_comparison",
        subject={"target": "environment:a"},
        reference_ids=["reference:a"],
        scope={"field": "status"},
        evidence_references=["evidence:a"],
        rule_references=["rule:a"],
        input_state_hash="state:before",
    )

    verifier_check_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": stable_hash(
            {"declared": "binding"}
        ),
        "verifier_id": "environment_snapshot_comparison",
        "check_id": check_identity["check_id"],
        "check_identity_hash": check_identity["check_identity_hash"],
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    verifier_check_binding["binding_hash"] = stable_hash(
        verifier_check_binding
    )

    execution_receipt = execute_declared_verifier(
        verifier_check_binding=verifier_check_binding,
        check_identity=check_identity,
        available_verifiers={
            "environment_snapshot_comparison": lambda _: result
        },
    )

    result_binding = bind_check_result(
        check_identity=check_identity,
        result=execution_receipt["result"],
        output_state_hash="state:after",
    )

    return execution_receipt, result_binding


def _rule(expected=None):
    if expected is None:
        expected = {"status": "COMPLETE"}

    return {
        "type": "exact_result_match",
        "expected_result": expected,
        "match_outcome": "SUPPORTS",
        "mismatch_outcome": "CONTRADICTS",
    }


def test_verified_matching_result_supports():
    execution_receipt, result_binding = _artifacts()

    outcome = build_verified_directional_check_outcome(
        execution_receipt=execution_receipt,
        result_binding=result_binding,
        evaluation_rule=_rule(),
    )

    assert outcome["matched"] is True
    assert outcome["outcome"] == "SUPPORTS"
    assert outcome["execution_receipt_hash"] == execution_receipt["receipt_hash"]
    assert outcome["result_binding_hash"] == result_binding["binding_hash"]
    assert outcome["result_hash"] == execution_receipt["result_hash"]
    assert outcome["truth_claimed"] is False
    assert outcome["accepted"] is False
    assert outcome["execution_authority"] == "NONE"
    assert outcome["write_authority"] == "NONE"

    body = dict(outcome)
    outcome_hash = body.pop("outcome_hash")
    assert outcome_hash == stable_hash(body)


def test_verified_mismatch_contradicts():
    execution_receipt, result_binding = _artifacts(
        {"status": "INCOMPLETE"}
    )

    outcome = build_verified_directional_check_outcome(
        execution_receipt=execution_receipt,
        result_binding=result_binding,
        evaluation_rule=_rule(),
    )

    assert outcome["matched"] is False
    assert outcome["outcome"] == "CONTRADICTS"


def test_rule_can_explicitly_return_unknown():
    execution_receipt, result_binding = _artifacts(
        {"status": "INCOMPLETE"}
    )
    rule = _rule()
    rule["mismatch_outcome"] = "UNKNOWN"

    outcome = build_verified_directional_check_outcome(
        execution_receipt=execution_receipt,
        result_binding=result_binding,
        evaluation_rule=rule,
    )

    assert outcome["matched"] is False
    assert outcome["outcome"] == "UNKNOWN"


def test_fabricated_self_hashed_execution_receipt_fails_closed():
    execution_receipt, result_binding = _artifacts()

    fabricated = dict(execution_receipt)
    fabricated["type"] = "fabricated_execution_receipt"
    body = {
        key: value
        for key, value in fabricated.items()
        if key != "receipt_hash"
    }
    fabricated["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="execution receipt type mismatch",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=fabricated,
            result_binding=result_binding,
            evaluation_rule=_rule(),
        )


def test_tampered_execution_receipt_fails_closed():
    execution_receipt, result_binding = _artifacts()

    execution_receipt["result"] = {"status": "TAMPERED"}

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="execution receipt hash mismatch",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=_rule(),
        )


def test_mismatched_check_id_fails_closed():
    execution_receipt, result_binding = _artifacts()

    result_binding["check_id"] = "check:b"
    body = {
        key: value
        for key, value in result_binding.items()
        if key != "binding_hash"
    }
    result_binding["binding_hash"] = stable_hash(body)

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="check_id mismatch",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=_rule(),
        )


def test_mismatched_check_identity_hash_fails_closed():
    execution_receipt, result_binding = _artifacts()

    result_binding["check_identity_hash"] = stable_hash(
        {"different": "identity"}
    )
    body = {
        key: value
        for key, value in result_binding.items()
        if key != "binding_hash"
    }
    result_binding["binding_hash"] = stable_hash(body)

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="check_identity_hash mismatch",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=_rule(),
        )


def test_result_binding_for_different_result_fails_closed():
    execution_receipt, result_binding = _artifacts()

    different_result = {"status": "DIFFERENT"}
    result_binding["result"] = different_result
    result_binding["result_hash"] = stable_hash(different_result)

    body = {
        key: value
        for key, value in result_binding.items()
        if key != "binding_hash"
    }
    result_binding["binding_hash"] = stable_hash(body)

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="result hash mismatch",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=_rule(),
        )


def test_tampered_result_binding_fails_closed():
    execution_receipt, result_binding = _artifacts()

    result_binding["output_state_hash"] = "state:tampered"

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="result binding hash mismatch",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=_rule(),
        )


def test_unsupported_rule_fails_closed():
    execution_receipt, result_binding = _artifacts()

    rule = _rule()
    rule["type"] = "natural_language_guess"

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="evaluation_rule type is unsupported",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=rule,
        )


def test_invalid_direction_fails_closed():
    execution_receipt, result_binding = _artifacts()

    rule = _rule()
    rule["match_outcome"] = "PROBABLY"

    with pytest.raises(
        VerifiedDirectionalCheckOutcomeError,
        match="match_outcome is invalid",
    ):
        build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=rule,
        )
