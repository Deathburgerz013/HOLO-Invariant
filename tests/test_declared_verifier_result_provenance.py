from holosim.canonical import stable_hash
from holosim.declared_verifier_result_provenance import (
    bind_declared_verifier_result_provenance,
)


def test_mismatched_check_identity_fails_closed():
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
        "check_id": "check:b",
        "check_identity_hash": "identity:b",
        "input_state_hash": "state:before",
        "result": {"status": "COMPLETE"},
        "result_hash": stable_hash({"status": "COMPLETE"}),
        "output_state_hash": "state:after",
        "justifier_reference": None,
        "accepted": False,
        "write_authority": "NONE",
    }
    result_binding["binding_hash"] = stable_hash(result_binding)

    try:
        bind_declared_verifier_result_provenance(
            verifier_check_binding=verifier_check_binding,
            result_binding=result_binding,
        )
    except Exception:
        pass
    else:
        raise AssertionError(
            "different check identities must not form one provenance chain"
        )
def test_matching_check_identity_forms_deterministic_provenance():
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

    first = bind_declared_verifier_result_provenance(
        verifier_check_binding=verifier_check_binding,
        result_binding=result_binding,
    )
    second = bind_declared_verifier_result_provenance(
        verifier_check_binding=verifier_check_binding,
        result_binding=result_binding,
    )

    assert first == second
    assert first["verifier_check_binding_hash"] == (
        verifier_check_binding["binding_hash"]
    )
    assert first["result_binding_hash"] == result_binding["binding_hash"]
    assert first["check_id"] == "check:a"
    assert first["check_identity_hash"] == "identity:a"
    assert first["execution_claimed"] is False
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"