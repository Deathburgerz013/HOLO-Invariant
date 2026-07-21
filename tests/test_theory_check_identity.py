from holosim.theory import evaluate_theory_state


def _theory():
    return {
        "theory_id": "t1",
        "statement": "A possibility",
        "basis": ["fixture basis"],
        "predictions": [
            {"prediction_id": "p1", "statement": "prediction p1"},
        ],
    }


def _check(*, evidence="fixture evidence", method="comparison"):
    return {
        "check_id": "c1",
        "prediction_id": "p1",
        "outcome": "CONSISTENT",
        "evidence": evidence,
        "method": method,
    }


def test_theory_receipt_embeds_shared_check_identity():
    receipt = evaluate_theory_state(_theory(), [_check()])

    assert receipt["version"] == 2
    assert len(receipt["check_identities"]) == 1

    identity = receipt["check_identities"][0]
    assert identity["type"] == "check_identity"
    assert identity["check_id"] == "c1"
    assert identity["check_type"] == "theory_prediction_check"
    assert identity["subject"] == {
        "theory_id": "t1",
        "prediction_id": "p1",
    }
    assert identity["reference_ids"] == ["theory:t1", "prediction:p1"]
    assert identity["scope"] == {"method": "comparison"}
    assert identity["evidence_references"] == ["fixture evidence"]
    assert identity["rule_references"] == []
    assert identity["input_state_hash"] == receipt["theory_hash"]
    assert identity["result_bound"] is False
    assert identity["accepted"] is False
    assert identity["write_authority"] == "NONE"
    assert len(identity["check_identity_hash"]) == 64


def test_theory_check_identity_changes_when_check_context_changes():
    original = evaluate_theory_state(_theory(), [_check()])
    changed_evidence = evaluate_theory_state(
        _theory(), [_check(evidence="different evidence")]
    )
    changed_method = evaluate_theory_state(
        _theory(), [_check(method="different method")]
    )

    original_hash = original["check_identities"][0]["check_identity_hash"]
    assert changed_evidence["check_identities"][0]["check_identity_hash"] != original_hash
    assert changed_method["check_identities"][0]["check_identity_hash"] != original_hash


def test_same_theory_check_reconstructs_same_identity():
    first = evaluate_theory_state(_theory(), [_check()])
    second = evaluate_theory_state(_theory(), [_check()])

    assert first["check_identities"] == second["check_identities"]
    assert first["receipt_hash"] == second["receipt_hash"]
