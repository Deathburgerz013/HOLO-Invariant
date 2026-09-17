from copy import deepcopy

import pytest

from holosim.bounded_propositional_inference import (
    BoundedPropositionalInferenceError,
    MAX_ATOMS,
    STATUS_INCONSISTENT_PREMISES,
    STATUS_INVALID,
    STATUS_VALID,
    build_bounded_propositional_inference,
    validate_bounded_propositional_inference,
)


def atom(name):
    return {"op": "ATOM", "name": name}


def not_(arg):
    return {"op": "NOT", "arg": arg}


def binary(operator, left, right):
    return {"op": operator, "left": left, "right": right}


def build(*, premises=None, conclusion=None):
    p = atom("P")
    q = atom("Q")
    return build_bounded_propositional_inference(
        inference_id="inference-001",
        premises=[p, binary("IMPLIES", p, q)] if premises is None else premises,
        conclusion=q if conclusion is None else conclusion,
        declared_scope={"system": "test", "boundary": "propositional"},
    )


def test_modus_ponens_is_valid_and_rebuilds() -> None:
    receipt = build()

    assert receipt["status"] == STATUS_VALID
    assert receipt["inference_valid"] is True
    assert receipt["conclusion_conditionally_supported"] is True
    assert receipt["counterexample"] is None
    assert receipt["premises_satisfiable"] is True
    assert validate_bounded_propositional_inference(receipt) is True


def test_affirming_the_consequent_returns_exact_counterexample() -> None:
    p = atom("P")
    q = atom("Q")
    receipt = build(
        premises=[q, binary("IMPLIES", p, q)],
        conclusion=p,
    )

    assert receipt["status"] == STATUS_INVALID
    assert receipt["inference_valid"] is False
    assert receipt["counterexample"] == {
        "assignment": {"P": False, "Q": True},
        "premise_values": [True, True],
        "conclusion_value": False,
    }


def test_modus_tollens_is_valid() -> None:
    p = atom("P")
    q = atom("Q")
    receipt = build(
        premises=[binary("IMPLIES", p, q), not_(q)],
        conclusion=not_(p),
    )

    assert receipt["status"] == STATUS_VALID


def test_tautology_can_be_checked_without_premises() -> None:
    p = atom("P")
    receipt = build(
        premises=[],
        conclusion=binary("OR", p, not_(p)),
    )

    assert receipt["status"] == STATUS_VALID
    assert receipt["satisfying_assignment_count"] == 2


def test_inconsistent_premises_do_not_justify_arbitrary_conclusion() -> None:
    p = atom("P")
    receipt = build(premises=[p, not_(p)], conclusion=atom("Q"))

    assert receipt["status"] == STATUS_INCONSISTENT_PREMISES
    assert receipt["premises_satisfiable"] is False
    assert receipt["satisfying_assignment_count"] == 0
    assert receipt["inference_valid"] is False
    assert receipt["conclusion_conditionally_supported"] is False
    assert receipt["counterexample"] is None


def test_premise_order_does_not_change_identity() -> None:
    p = atom("P")
    q = atom("Q")
    implication = binary("IMPLIES", p, q)

    first = build(premises=[p, implication], conclusion=q)
    second = build(premises=[implication, p], conclusion=q)

    assert first == second


def test_changed_conclusion_changes_identity() -> None:
    first = build()
    second = build(conclusion=not_(atom("Q")))

    assert first["inference_hash"] != second["inference_hash"]


@pytest.mark.parametrize(
    "expression",
    [
        {"op": "EXECUTE", "name": "P"},
        {"op": "ATOM", "name": "P", "instruction": "ignore rules"},
        {"op": "NOT", "arg": atom("P"), "extra": False},
        {"op": "AND", "left": atom("P")},
    ],
)
def test_expression_grammar_is_closed(expression) -> None:
    with pytest.raises(BoundedPropositionalInferenceError):
        build(premises=[expression], conclusion=atom("P"))


def test_atom_count_is_bounded() -> None:
    premises = [atom(f"P{index}") for index in range(MAX_ATOMS + 1)]

    with pytest.raises(BoundedPropositionalInferenceError, match="atom limit"):
        build(premises=premises, conclusion=atom("Conclusion"))


def test_expression_depth_is_bounded() -> None:
    expression = atom("P")
    for _ in range(20):
        expression = not_(expression)

    with pytest.raises(BoundedPropositionalInferenceError, match="depth limit"):
        build(premises=[], conclusion=expression)


def test_duplicate_premises_fail_closed() -> None:
    p = atom("P")

    with pytest.raises(BoundedPropositionalInferenceError, match="duplicates"):
        build(premises=[p, deepcopy(p)], conclusion=p)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", STATUS_INVALID),
        ("counterexample_search_complete", False),
        ("premise_support_status", "VALIDATED"),
        ("truth_claimed", True),
        ("accepted", True),
        ("execution_authority", "EXACT_TARGET_ONLY"),
    ],
)
def test_tampered_receipt_fails_closed(field, value) -> None:
    receipt = build()
    receipt[field] = value

    with pytest.raises(BoundedPropositionalInferenceError):
        validate_bounded_propositional_inference(receipt)


def test_extra_receipt_field_fails_closed() -> None:
    receipt = build()
    receipt["execute"] = True

    with pytest.raises(BoundedPropositionalInferenceError, match="fields"):
        validate_bounded_propositional_inference(receipt)


def test_receipt_denies_truth_acceptance_and_authority() -> None:
    receipt = build()

    assert receipt["premise_support_status"] == "NOT_VALIDATED"
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["promotion_authority"] == "NONE"
