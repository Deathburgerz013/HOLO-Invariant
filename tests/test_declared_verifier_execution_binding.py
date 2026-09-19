from holosim.canonical import stable_hash
from holosim.declared_verifier_execution_binding import (
    bind_declared_verifier_execution,
)


def test_execution_must_bind_same_exact_check_and_result():
    verifier_check_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": "declared-binding:a",
        "verifier_id": "environment_snapshot_comparison",
        "check_id": "check:a",
        "check_identity_hash": "identity:a",
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    verifier_check_binding["binding_hash"] = stable_hash(
        verifier_check_binding
    )

    result_binding = {
        "type": "check_result_binding",
        "version": 1,
        "check_id": "check:a",
        "check_identity_hash": "identity:a",
        "input_state_hash": "state:before",
        "result": {"status": "COMPLETE"},
        "result_hash": stable_hash({"status": "COMPLETE"}),
        "output_state_hash": "state:after",
        "justifier_reference": None,
        "accepted": False,
        "write_authority": "NONE",
    }
    result_binding["binding_hash"] = stable_hash(result_binding)

    execution_receipt_hash = stable_hash(
        {
            "verifier_id": "environment_snapshot_comparison",
            "check_id": "check:a",
            "check_identity_hash": "identity:a",
            "result_binding_hash": result_binding["binding_hash"],
        }
    )

    first = bind_declared_verifier_execution(
        verifier_check_binding=verifier_check_binding,
        execution_receipt_hash=execution_receipt_hash,
        result_binding=result_binding,
    )
    second = bind_declared_verifier_execution(
        verifier_check_binding=verifier_check_binding,
        execution_receipt_hash=execution_receipt_hash,
        result_binding=result_binding,
    )

    assert first == second
    assert first["verifier_id"] == "environment_snapshot_comparison"
    assert first["check_id"] == "check:a"
    assert first["check_identity_hash"] == "identity:a"
    assert first["result_binding_hash"] == result_binding["binding_hash"]
    assert first["execution_receipt_hash"] == execution_receipt_hash
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"
def _base_bindings():
    verifier_check_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": "declared-binding:a",
        "verifier_id": "environment_snapshot_comparison",
        "check_id": "check:a",
        "check_identity_hash": "identity:a",
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    verifier_check_binding["binding_hash"] = stable_hash(
        verifier_check_binding
    )

    result_binding = {
        "type": "check_result_binding",
        "version": 1,
        "check_id": "check:a",
        "check_identity_hash": "identity:a",
        "input_state_hash": "state:before",
        "result": {"status": "COMPLETE"},
        "result_hash": stable_hash({"status": "COMPLETE"}),
        "output_state_hash": "state:after",
        "justifier_reference": None,
        "accepted": False,
        "write_authority": "NONE",
    }
    result_binding["binding_hash"] = stable_hash(result_binding)

    return verifier_check_binding, result_binding


def test_mismatched_check_id_fails_closed():
    verifier_check_binding, result_binding = _base_bindings()
    result_binding["check_id"] = "check:b"
    result_binding["binding_hash"] = stable_hash(
        {
            key: value
            for key, value in result_binding.items()
            if key != "binding_hash"
        }
    )

    try:
        bind_declared_verifier_execution(
            verifier_check_binding=verifier_check_binding,
            execution_receipt_hash=stable_hash({"execution": "a"}),
            result_binding=result_binding,
        )
    except Exception:
        pass
    else:
        raise AssertionError("different check ids must fail closed")


def test_mismatched_check_identity_fails_closed():
    verifier_check_binding, result_binding = _base_bindings()
    result_binding["check_identity_hash"] = "identity:b"
    result_binding["binding_hash"] = stable_hash(
        {
            key: value
            for key, value in result_binding.items()
            if key != "binding_hash"
        }
    )

    try:
        bind_declared_verifier_execution(
            verifier_check_binding=verifier_check_binding,
            execution_receipt_hash=stable_hash({"execution": "a"}),
            result_binding=result_binding,
        )
    except Exception:
        pass
    else:
        raise AssertionError("different check identities must fail closed")


def test_tampered_verifier_check_binding_fails_closed():
    verifier_check_binding, result_binding = _base_bindings()
    verifier_check_binding["verifier_id"] = "different_verifier"

    try:
        bind_declared_verifier_execution(
            verifier_check_binding=verifier_check_binding,
            execution_receipt_hash=stable_hash({"execution": "a"}),
            result_binding=result_binding,
        )
    except Exception:
        pass
    else:
        raise AssertionError("tampered verifier binding must fail closed")


def test_tampered_result_binding_fails_closed():
    verifier_check_binding, result_binding = _base_bindings()
    result_binding["result"] = {"status": "DIFFERENT"}

    try:
        bind_declared_verifier_execution(
            verifier_check_binding=verifier_check_binding,
            execution_receipt_hash=stable_hash({"execution": "a"}),
            result_binding=result_binding,
        )
    except Exception:
        pass
    else:
        raise AssertionError("tampered result binding must fail closed")


def test_invalid_execution_receipt_hash_fails_closed():
    verifier_check_binding, result_binding = _base_bindings()

    try:
        bind_declared_verifier_execution(
            verifier_check_binding=verifier_check_binding,
            execution_receipt_hash="not-a-sha256",
            result_binding=result_binding,
        )
    except Exception:
        pass
    else:
        raise AssertionError("invalid execution receipt hash must fail closed")