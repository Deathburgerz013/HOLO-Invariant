from copy import deepcopy

import pytest

from holosim.functional_motion_equivalence import (
    DIVERGENT_MOTION,
    EQUIVALENT_MOTION,
    INCOMPARABLE,
    FunctionalMotionEquivalenceError,
    build_functional_motion_trace,
    compare_functional_motion,
    validate_functional_motion_receipt,
    validate_functional_motion_trace,
)


def case(case_id="one", *, after=1, output="stored", constraints=None):
    return {
        "case_id": case_id,
        "input": {"value": 1},
        "constraints": constraints or {"capacity": 2},
        "before_observable": {"stored": 0},
        "after_observable": {"stored": after},
        "output_observable": output,
        "effects": ["state:stored"],
        "evidence_reference": f"run:{case_id}",
    }


def trace(implementation_id, label, cases=None, observer="observer:store:v1"):
    return build_functional_motion_trace(
        implementation_id=implementation_id,
        implementation_label=label,
        function_id="STORE",
        observer_contract_id=observer,
        cases=cases or [case()],
        provenance={"runner": "bounded-reproduction:v1"},
    )


def test_changed_words_with_same_motion_are_equivalent():
    receipt = compare_functional_motion(
        trace("a", "retain information"),
        trace("b", "preserve recoverable state"),
    )
    assert receipt["labels_changed"] is True
    assert receipt["classification"] == EQUIVALENT_MOTION
    assert receipt["equivalent_within_declared_cases"] is True
    assert receipt["implementations_declared_identical"] is False
    assert validate_functional_motion_receipt(receipt) is True


def test_same_words_with_changed_motion_are_divergent():
    receipt = compare_functional_motion(
        trace("a", "store"),
        trace("b", "store", [case(after=0)]),
    )
    assert receipt["labels_changed"] is False
    assert receipt["classification"] == DIVERGENT_MOTION
    assert receipt["divergent_cases"][0]["changed_observables"] == [
        "after_observable"
    ]


def test_different_constraints_are_incomparable_not_divergent():
    receipt = compare_functional_motion(
        trace("a", "store"),
        trace("b", "store", [case(constraints={"capacity": 1})]),
    )
    assert receipt["classification"] == INCOMPARABLE
    assert receipt["incompatibilities"] == ["one:constraints"]
    assert receipt["divergent_cases"] == []


def test_missing_case_is_incomparable():
    receipt = compare_functional_motion(
        trace("a", "store", [case("one"), case("two")]),
        trace("b", "store", [case("one")]),
    )
    assert receipt["classification"] == INCOMPARABLE
    assert receipt["incompatibilities"] == ["case_ids"]


def test_case_order_is_canonicalized():
    first = trace("a", "store", [case("two"), case("one")])
    second = trace("a", "store", [case("one"), case("two")])
    assert first == second
    assert validate_functional_motion_trace(first) is True


def test_tampered_trace_fails_closed():
    value = trace("a", "store")
    value["cases"][0]["after_observable"] = {"stored": 999}
    with pytest.raises(FunctionalMotionEquivalenceError, match="hash mismatch"):
        validate_functional_motion_trace(value)


def test_tampered_receipt_fails_closed():
    receipt = compare_functional_motion(trace("a", "store"), trace("b", "keep"))
    tampered = deepcopy(receipt)
    tampered["labels_changed"] = False
    with pytest.raises(FunctionalMotionEquivalenceError, match="hash mismatch"):
        validate_functional_motion_receipt(tampered)
