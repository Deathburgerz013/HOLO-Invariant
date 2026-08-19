from copy import deepcopy

import pytest

from holosim.environment_invariant_receipts import (
    EnvironmentInvariantReceiptError,
    evaluate_environment_invariant,
    verify_environment_invariant_receipt,
)


ENVIRONMENT = {
    "python": "3.13.7",
    "platform": "win32",
    "implementation": "CPython",
}

SCOPE = {
    "domain": "computation_systems",
    "conditions": [
        "canonical JSON encoding",
        "declared local environment",
    ],
}


def evaluate(check, **overrides):
    arguments = {
        "invariant_id": "INV-CANONICAL-JSON-001",
        "statement": (
            "Equivalent declared mappings produce identical "
            "canonical encodings."
        ),
        "scope": SCOPE,
        "environment": ENVIRONMENT,
        "environment_probe": lambda: ENVIRONMENT,
        "check_id": "canonical-json-order-independence",
        "check": check,
        "observed_at": "2026-08-19T19:00:00Z",
        "evidence": {
            "left": '{"a":1,"b":2}',
            "right": '{"a":1,"b":2}',
        },
    }
    arguments.update(overrides)
    return evaluate_environment_invariant(**arguments)


@pytest.mark.parametrize(
    ("observed", "status"),
    [
        (True, "HELD"),
        (False, "FAILED"),
        (None, "UNKNOWN"),
    ],
)
def test_environment_observation_has_bounded_status(
    observed,
    status,
):
    calls = []

    def check():
        calls.append(True)
        return observed

    receipt = evaluate(check)

    assert calls == [True]
    assert receipt["status"] == status
    assert receipt["constraint_authority"] == "ENVIRONMENT"
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["canonical_mutation"] is False
    assert verify_environment_invariant_receipt(receipt) is True


def test_environment_mismatch_is_stale_without_running_check():
    calls = []

    def check():
        calls.append(True)
        return True

    receipt = evaluate(
        check,
        expected_environment_fingerprint="different-environment",
    )

    assert calls == []
    assert receipt["status"] == "STALE"
    assert receipt["observed"] is None
    assert receipt["stale_reason"] == "ENVIRONMENT_FINGERPRINT_MISMATCH"
    assert verify_environment_invariant_receipt(receipt) is True


def test_check_exception_becomes_unknown_evidence():
    def check():
        raise RuntimeError("simulated observation failure")

    receipt = evaluate(check)

    assert receipt["status"] == "UNKNOWN"
    assert receipt["observed"] is None
    assert receipt["error"] == {
        "type": "RuntimeError",
        "message": "simulated observation failure",
    }
    assert verify_environment_invariant_receipt(receipt) is True


def test_receipt_is_deterministic_for_identical_observation():
    first = evaluate(lambda: True)
    second = evaluate(lambda: True)

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_tampered_receipt_is_rejected():
    receipt = evaluate(lambda: True)
    tampered = deepcopy(receipt)
    tampered["status"] = "FAILED"

    with pytest.raises(
        EnvironmentInvariantReceiptError,
        match="receipt hash mismatch",
    ):
        verify_environment_invariant_receipt(tampered)


def test_inputs_must_be_closed_json_values():
    with pytest.raises(
        EnvironmentInvariantReceiptError,
        match="environment must contain only JSON values",
    ):
        evaluate(
            lambda: True,
            environment={"machine": object()},
        )


def test_boolean_check_contract_is_strict():
    receipt = evaluate(lambda: "yes")

    assert receipt["status"] == "UNKNOWN"
    assert receipt["observed"] is None
    assert receipt["error"]["type"] == "InvalidCheckResult"
    assert verify_environment_invariant_receipt(receipt) is True
def test_declared_environment_must_match_observed_environment():
    calls = []

    def check():
        calls.append("check")
        return True

    def environment_probe():
        calls.append("probe")
        return {
            **ENVIRONMENT,
            "python": "different-runtime",
        }

    receipt = evaluate(
        check,
        environment_probe=environment_probe,
    )

    assert calls == ["probe"]
    assert receipt["status"] == "STALE"
    assert receipt["observed"] is None
    assert receipt["stale_reason"] == "DECLARED_ENVIRONMENT_MISMATCH"
    assert receipt["declared_environment"] == ENVIRONMENT
    assert receipt["observed_environment"]["python"] == "different-runtime"
    assert verify_environment_invariant_receipt(receipt) is True