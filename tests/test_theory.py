import hashlib
import json

import pytest

import holosim.theory as theory_module
from holosim.theory import (
    TheoryStateError,
    check_theory_receipt_current,
    evaluate_theory_state,
)


def prediction(prediction_id, statement=None):
    return {
        "prediction_id": prediction_id,
        "statement": statement or f"prediction {prediction_id}",
    }


def theory(predictions=None, basis=None, theory_id="t1", statement="A possibility"):
    return {
        "theory_id": theory_id,
        "statement": statement,
        "basis": ["x + y permits z"] if basis is None else basis,
        "predictions": (
            [prediction("p1"), prediction("p2")]
            if predictions is None
            else predictions
        ),
    }


def check(
    check_id,
    prediction_id,
    outcome,
    evidence="fixture evidence",
    method="comparison",
):
    return {
        "check_id": check_id,
        "prediction_id": prediction_id,
        "outcome": outcome,
        "evidence": evidence,
        "method": method,
    }


def rehash(receipt):
    body = dict(receipt)
    body.pop("receipt_hash", None)
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(encoded).hexdigest()


def test_unchecked_theory_is_possible_and_navigates_to_first_prediction():
    receipt = evaluate_theory_state(theory(), [])

    assert receipt["state"] == "POSSIBLE"
    assert receipt["checked_prediction_ids"] == []
    assert receipt["unchecked_prediction_ids"] == ["p1", "p2"]
    assert receipt["next_missing_check"] == "p1"
    assert receipt["next_action"] == "CHECK:p1"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_consistent_check_advances_navigation_without_claiming_truth():
    receipt = evaluate_theory_state(
        theory(), [check("c1", "p1", "CONSISTENT")]
    )

    assert receipt["state"] == "POSSIBLE"
    assert receipt["checked_prediction_ids"] == ["p1"]
    assert receipt["unchecked_prediction_ids"] == ["p2"]
    assert receipt["next_missing_check"] == "p2"
    assert receipt["next_action"] == "CHECK:p2"
    assert "true, proven, probable" in receipt["interpretation_notice"]


def test_all_consistent_checks_still_leave_theory_possible():
    receipt = evaluate_theory_state(
        theory(),
        [
            check("c1", "p1", "CONSISTENT"),
            check("c2", "p2", "CONSISTENT"),
        ],
    )

    assert receipt["state"] == "POSSIBLE"
    assert receipt["unchecked_prediction_ids"] == []
    assert receipt["next_missing_check"] is None
    assert receipt["next_action"] == "SEEK_NEW_FALSIFIER"
    assert "TRUE" not in receipt.values()
    assert "PROVEN" not in receipt.values()


def test_unavailable_check_does_not_resolve_prediction():
    receipt = evaluate_theory_state(
        theory(), [check("c1", "p1", "UNAVAILABLE")]
    )

    assert receipt["state"] == "POSSIBLE"
    assert receipt["checked_prediction_ids"] == []
    assert receipt["unchecked_prediction_ids"] == ["p1", "p2"]
    assert receipt["unavailable_check_ids"] == ["c1"]
    assert receipt["next_missing_check"] == "p1"


def test_later_consistent_check_can_resolve_previously_unavailable_prediction():
    receipt = evaluate_theory_state(
        theory(),
        [
            check("c1", "p1", "UNAVAILABLE"),
            check("c2", "p1", "CONSISTENT"),
        ],
    )

    assert receipt["checked_prediction_ids"] == ["p1"]
    assert receipt["unavailable_check_ids"] == ["c1"]
    assert receipt["next_missing_check"] == "p2"


def test_one_contradiction_falsifies_theory():
    receipt = evaluate_theory_state(
        theory(), [check("c1", "p1", "CONTRADICTED")]
    )

    assert receipt["state"] == "FALSIFIED"
    assert receipt["contradicting_check_ids"] == ["c1"]
    assert receipt["next_action"] == "REVISE_OR_REPLACE_THEORY"
    assert receipt["accepted"] is False


def test_contradiction_remains_visible_after_other_consistent_checks():
    receipt = evaluate_theory_state(
        theory(),
        [
            check("c1", "p1", "CONSISTENT"),
            check("c2", "p2", "CONTRADICTED"),
            check("c3", "p2", "CONSISTENT"),
        ],
    )

    assert receipt["state"] == "FALSIFIED"
    assert receipt["contradicting_check_ids"] == ["c2"]
    assert receipt["checked_prediction_ids"] == ["p1", "p2"]


def test_theory_without_predictions_is_untestable():
    receipt = evaluate_theory_state(theory(predictions=[]), [])

    assert receipt["state"] == "UNTESTABLE"
    assert receipt["next_missing_check"] is None
    assert receipt["next_action"] == "DEFINE_PREDICTION"


def test_receipt_binds_theory_and_ordered_checks():
    receipt = evaluate_theory_state(
        theory(), [check("c1", "p1", "CONSISTENT")]
    )

    assert len(receipt["theory_hash"]) == 64
    assert len(receipt["check_hashes"]) == 1
    assert len(receipt["check_hashes"][0]) == 64
    assert len(receipt["receipt_hash"]) == 64
    assert receipt["current"] is True
    assert receipt["stale_reason"] is None


def test_receipt_is_current_for_same_theory_and_checks():
    candidate = theory()
    checks = [check("c1", "p1", "CONSISTENT")]
    receipt = evaluate_theory_state(candidate, checks)

    assert check_theory_receipt_current(receipt, candidate, checks) == {
        "current": True,
        "stale_reason": None,
    }


@pytest.mark.parametrize(
    "changed",
    [
        theory(statement="Changed possibility"),
        theory(basis=["different basis"]),
        theory(predictions=[prediction("p2"), prediction("p1")]),
        theory(predictions=[prediction("p1")]),
    ],
)
def test_theory_change_stales_receipt_before_old_checks_are_reinterpreted(changed):
    original = theory()
    checks = [check("c1", "p2", "CONSISTENT")]
    receipt = evaluate_theory_state(original, checks)

    assert check_theory_receipt_current(receipt, changed, checks) == {
        "current": False,
        "stale_reason": "THEORY_CHANGED",
    }


@pytest.mark.parametrize(
    "changed_checks",
    [
        [check("c1", "p1", "CONTRADICTED")],
        [check("c1", "p1", "CONSISTENT", evidence="new evidence")],
        [check("c2", "p2", "CONSISTENT"), check("c1", "p1", "CONSISTENT")],
        [],
    ],
)
def test_check_history_change_stales_receipt(changed_checks):
    candidate = theory()
    original_checks = [
        check("c1", "p1", "CONSISTENT"),
        check("c2", "p2", "CONSISTENT"),
    ]
    receipt = evaluate_theory_state(candidate, original_checks)

    assert check_theory_receipt_current(receipt, candidate, changed_checks) == {
        "current": False,
        "stale_reason": "CHECK_HISTORY_CHANGED",
    }


def test_unknown_prediction_reference_fails_closed():
    with pytest.raises(TheoryStateError, match="unknown prediction_id"):
        evaluate_theory_state(
            theory(), [check("c1", "missing", "CONSISTENT")]
        )


def test_duplicate_prediction_ids_fail_closed():
    with pytest.raises(TheoryStateError, match="prediction_id values must be unique"):
        evaluate_theory_state(
            theory(predictions=[prediction("same"), prediction("same")]), []
        )


def test_duplicate_check_ids_fail_closed():
    with pytest.raises(TheoryStateError, match="check_id values must be unique"):
        evaluate_theory_state(
            theory(),
            [
                check("same", "p1", "CONSISTENT"),
                check("same", "p2", "CONSISTENT"),
            ],
        )


@pytest.mark.parametrize("outcome", ["HELD", "FAILED", "TRUE", "", None, 1])
def test_invalid_check_outcome_fails_closed(outcome):
    with pytest.raises(TheoryStateError, match="outcome must be"):
        evaluate_theory_state(theory(), [check("c1", "p1", outcome)])


@pytest.mark.parametrize(
    "candidate",
    [
        "not-an-object",
        {"theory_id": "t1"},
        {
            "theory_id": "t1",
            "statement": "possible",
            "basis": [],
            "predictions": [],
            "extra": True,
        },
    ],
)
def test_invalid_theory_shape_fails_closed(candidate):
    with pytest.raises(TheoryStateError):
        evaluate_theory_state(candidate, [])


@pytest.mark.parametrize(
    "candidate",
    [
        "not-an-object",
        {"prediction_id": "p1"},
        {"prediction_id": "p1", "statement": "s", "extra": True},
    ],
)
def test_invalid_prediction_shape_fails_closed(candidate):
    with pytest.raises(TheoryStateError):
        evaluate_theory_state(theory(predictions=[candidate]), [])


@pytest.mark.parametrize(
    "candidate",
    [
        "not-an-object",
        {"check_id": "c1"},
        {
            **check("c1", "p1", "CONSISTENT"),
            "extra": True,
        },
    ],
)
def test_invalid_check_shape_fails_closed(candidate):
    with pytest.raises(TheoryStateError):
        evaluate_theory_state(theory(), [candidate])


class StringSubclass(str):
    __hash__ = str.__hash__

    def __eq__(self, other):
        raise RuntimeError("hostile equality")


@pytest.mark.parametrize("target", ["theory", "prediction", "check"])
def test_hostile_string_subclass_keys_fail_with_domain_error(target):
    if target == "theory":
        candidate = {
            StringSubclass("theory_id"): "t1",
            StringSubclass("statement"): "possible",
            StringSubclass("basis"): [],
            StringSubclass("predictions"): [],
        }
        checks = []
    elif target == "prediction":
        candidate = theory(
            predictions=[
                {
                    StringSubclass("prediction_id"): "p1",
                    StringSubclass("statement"): "prediction",
                }
            ]
        )
        checks = []
    else:
        candidate = theory()
        checks = [
            {
                StringSubclass("check_id"): "c1",
                StringSubclass("prediction_id"): "p1",
                StringSubclass("outcome"): "CONSISTENT",
                StringSubclass("evidence"): "evidence",
                StringSubclass("method"): "method",
            }
        ]

    with pytest.raises(TheoryStateError, match="keys must be plain strings"):
        evaluate_theory_state(candidate, checks)


@pytest.mark.parametrize(
    "value",
    ["", "   ", StringSubclass("hostile"), "\ud800", "x" * 16385],
)
def test_invalid_theory_id_fails_closed(value):
    with pytest.raises(TheoryStateError, match="theory_id"):
        evaluate_theory_state(theory(theory_id=value), [])


@pytest.mark.parametrize("field", ["basis", "predictions", "checks"])
def test_text_is_not_silently_used_as_a_collection(field):
    candidate = theory()
    checks = []
    if field == "basis":
        candidate["basis"] = "not a list"
    elif field == "predictions":
        candidate["predictions"] = "not a list"
    else:
        checks = "not a list"

    with pytest.raises(TheoryStateError, match="collection"):
        evaluate_theory_state(candidate, checks)


def test_noniterable_checks_fail_with_domain_error():
    with pytest.raises(TheoryStateError, match="checks must be iterable"):
        evaluate_theory_state(theory(), None)


def test_generator_failure_fails_with_domain_error():
    def broken():
        yield check("c1", "p1", "CONSISTENT")
        raise RuntimeError("generator failed")

    with pytest.raises(TheoryStateError, match="could not be materialized"):
        evaluate_theory_state(theory(), broken())


def test_item_limit_fails_closed(monkeypatch):
    monkeypatch.setattr(theory_module, "MAX_THEORY_ITEMS", 2)

    with pytest.raises(TheoryStateError, match="cannot exceed 2"):
        evaluate_theory_state(
            theory(),
            (
                check(f"c{index}", "p1", "CONSISTENT")
                for index in range(3)
            ),
        )


def test_evaluation_does_not_mutate_inputs():
    candidate = theory()
    checks = [check("c1", "p1", "CONSISTENT")]
    before_theory = json.loads(json.dumps(candidate))
    before_checks = json.loads(json.dumps(checks))

    evaluate_theory_state(candidate, checks)

    assert candidate == before_theory
    assert checks == before_checks


def test_check_generator_is_consumed_once_in_currentness():
    candidate = theory()
    original = [check("c1", "p1", "CONSISTENT")]
    receipt = evaluate_theory_state(candidate, original)
    yielded = []

    def checks():
        for item in original:
            yielded.append(item["check_id"])
            yield item

    assert check_theory_receipt_current(receipt, candidate, checks())["current"] is True
    assert yielded == ["c1"]


def test_unrehashed_tampering_fails_integrity():
    receipt = evaluate_theory_state(theory(), [])
    receipt["state"] = "FALSIFIED"

    with pytest.raises(TheoryStateError, match="hash mismatch"):
        check_theory_receipt_current(receipt, theory(), [])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("accepted", True, "cannot grant acceptance"),
        ("write_authority", "ALL", "cannot grant write authority"),
    ],
)
def test_rehashed_authority_tampering_fails_closed(field, value, message):
    receipt = evaluate_theory_state(theory(), [])
    receipt[field] = value
    rehash(receipt)

    with pytest.raises(TheoryStateError, match=message):
        check_theory_receipt_current(receipt, theory(), [])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda receipt: receipt.update(state="TRUE"),
        lambda receipt: receipt.update(next_action="ACCEPT_THEORY"),
        lambda receipt: receipt["unchecked_prediction_ids"].clear(),
        lambda receipt: receipt["check_hashes"].append("0" * 64),
        lambda receipt: receipt["theory"].update(statement="forged"),
    ],
)
def test_rehashed_semantic_tampering_fails_closed(mutation):
    receipt = evaluate_theory_state(theory(), [])
    mutation(receipt)
    rehash(receipt)

    with pytest.raises(TheoryStateError, match="internally inconsistent"):
        check_theory_receipt_current(receipt, theory(), [])


def test_rehashed_missing_field_fails_schema_before_stale_path():
    receipt = evaluate_theory_state(theory(), [])
    receipt.pop("next_action")
    rehash(receipt)

    with pytest.raises(TheoryStateError, match="schema"):
        check_theory_receipt_current(receipt, theory(statement="changed"), [])


def test_boolean_version_fails_closed():
    receipt = evaluate_theory_state(theory(), [])
    receipt["version"] = True
    rehash(receipt)

    with pytest.raises(TheoryStateError, match="version"):
        check_theory_receipt_current(receipt, theory(), [])


def test_nonfinite_receipt_value_fails_with_domain_error():
    receipt = evaluate_theory_state(theory(), [])
    receipt["unexpected_number"] = float("nan")

    with pytest.raises(TheoryStateError, match="finite"):
        check_theory_receipt_current(receipt, theory(), [])


def test_cyclic_receipt_fails_with_domain_error():
    receipt = evaluate_theory_state(theory(), [])
    receipt["cycle"] = receipt

    with pytest.raises(TheoryStateError, match="cycles"):
        check_theory_receipt_current(receipt, theory(), [])


def test_excessively_deep_receipt_fails_with_domain_error():
    receipt = evaluate_theory_state(theory(), [])
    nested = []
    cursor = nested
    for _ in range(12):
        child = []
        cursor.append(child)
        cursor = child
    receipt["deep"] = nested

    with pytest.raises(TheoryStateError, match="depth"):
        check_theory_receipt_current(receipt, theory(), [])