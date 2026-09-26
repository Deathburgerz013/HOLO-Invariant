from copy import deepcopy

import pytest

from holosim.bounded_python_callable_identity import (
    derive_python_callable_identity,
)
from holosim.compression_observer_coverage import (
    CompressionObserverCoverageError,
    evaluate_compression_observer_coverage,
    verify_compression_observer_coverage_receipt,
)


def value_observer(value, context):
    return value["value"]


def authority_observer(value, context):
    return value["authority"]


def provenance_observer(value, context):
    return value["provenance"]


def evidence_binding_observer(value, context):
    return value["evidence_binding"]


OBSERVERS = {
    "authority": authority_observer,
    "provenance": provenance_observer,
    "value": value_observer,
    "evidence_binding": evidence_binding_observer,
}


def _identities(names):
    return {
        name: derive_python_callable_identity(OBSERVERS[name])[
            "callable_identity"
        ]
        for name in names
    }


def _evaluate(required=None, declared=None):
    required_names = (
        ["authority", "provenance", "value"]
        if required is None
        else required
    )
    declared_names = (
        ["authority", "provenance", "value"]
        if declared is None
        else declared
    )

    return evaluate_compression_observer_coverage(
        required_observations=required_names,
        declared_observers=declared_names,
        observer_identities=_identities(declared_names),
        requirement_basis_ref="verification-contract:1",
    )


def test_exact_observer_coverage_is_complete():
    receipt = _evaluate()

    assert receipt["status"] == "COVERAGE_COMPLETE"
    assert receipt["coverage_complete"] is True
    assert receipt["missing_observations"] == []
    assert receipt["extra_observers"] == []


def test_missing_required_observer_fails_coverage():
    receipt = _evaluate(declared=["authority", "value"])

    assert receipt["status"] == "COVERAGE_INCOMPLETE"
    assert receipt["coverage_complete"] is False
    assert receipt["missing_observations"] == ["provenance"]


def test_extra_observer_does_not_invalidate_required_coverage():
    receipt = _evaluate(
        declared=[
            "authority",
            "provenance",
            "value",
            "evidence_binding",
        ]
    )

    assert receipt["status"] == "COVERAGE_COMPLETE"
    assert receipt["extra_observers"] == ["evidence_binding"]


def test_input_order_does_not_change_receipt_identity():
    first = _evaluate()

    declared = ["provenance", "value", "authority"]

    second = evaluate_compression_observer_coverage(
        required_observations=["value", "authority", "provenance"],
        declared_observers=declared,
        observer_identities=_identities(declared),
        requirement_basis_ref="verification-contract:1",
    )

    assert first == second


def test_observer_identities_are_bound_to_receipt():
    receipt = _evaluate()

    assert set(receipt["observer_identities"]) == {
        "authority",
        "provenance",
        "value",
    }
    assert all(
        len(identity) == 64
        for identity in receipt["observer_identities"].values()
    )


def test_missing_observer_identity_fails_closed():
    with pytest.raises(
        CompressionObserverCoverageError,
        match="exactly match declared_observers",
    ):
        evaluate_compression_observer_coverage(
            required_observations=["authority", "value"],
            declared_observers=["authority", "value"],
            observer_identities=_identities(["value"]),
            requirement_basis_ref="verification-contract:1",
        )


def test_extra_observer_identity_fails_closed():
    with pytest.raises(
        CompressionObserverCoverageError,
        match="exactly match declared_observers",
    ):
        evaluate_compression_observer_coverage(
            required_observations=["value"],
            declared_observers=["value"],
            observer_identities=_identities(["value", "authority"]),
            requirement_basis_ref="verification-contract:1",
        )


def test_changed_callable_identity_changes_coverage_receipt():
    first = _evaluate()

    declared = ["authority", "provenance", "value"]
    identities = _identities(declared)
    identities["value"] = derive_python_callable_identity(
        authority_observer
    )["callable_identity"]

    second = evaluate_compression_observer_coverage(
        required_observations=declared,
        declared_observers=declared,
        observer_identities=identities,
        requirement_basis_ref="verification-contract:1",
    )

    assert first["receipt_id"] != second["receipt_id"]
    assert (
        first["observer_identities"]["value"]
        != second["observer_identities"]["value"]
    )


def test_receipt_carries_no_truth_or_compression_authority():
    receipt = _evaluate()

    assert receipt["observation_truth_verified"] is False
    assert receipt["compression_preservation_verified"] is False
    assert receipt["compression_authorized"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_receipt_replays_validly():
    receipt = _evaluate()

    result = verify_compression_observer_coverage_receipt(receipt)

    assert result["valid"] is True
    assert result["violations"] == []
    assert result["receipt_id"] == receipt["receipt_id"]
    assert result["expected_receipt_id"] == receipt["receipt_id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "COVERAGE_INCOMPLETE"),
        ("coverage_complete", False),
        ("missing_observations", ["fabricated"]),
        ("compression_preservation_verified", True),
        ("accepted", True),
        ("write_authority", "WRITE"),
    ],
)
def test_semantic_forgery_fails_replay(field, value):
    receipt = _evaluate()
    forged = deepcopy(receipt)
    forged[field] = value

    result = verify_compression_observer_coverage_receipt(forged)

    assert result["valid"] is False
    assert result["violations"]


def test_tampered_observer_identity_fails_replay():
    receipt = _evaluate()
    forged = deepcopy(receipt)
    forged["observer_identities"]["value"] = "0" * 64

    result = verify_compression_observer_coverage_receipt(forged)

    assert result["valid"] is False
    assert result["violations"]


def test_added_field_fails_replay():
    receipt = _evaluate()
    forged = deepcopy(receipt)
    forged["invented"] = True

    result = verify_compression_observer_coverage_receipt(forged)

    assert result["valid"] is False


@pytest.mark.parametrize(
    "required,declared",
    [
        ([], ["value"]),
        (["value"], []),
        ("value", ["value"]),
        (["value"], "value"),
        ([""], ["value"]),
        (["value"], [" "]),
        (["value", "value"], ["value"]),
        (["value"], ["value", "value"]),
        ([1], ["value"]),
        (["value"], [1]),
    ],
)
def test_malformed_observer_sets_fail_closed(required, declared):
    with pytest.raises(
        (CompressionObserverCoverageError, KeyError, TypeError)
    ):
        _evaluate(required=required, declared=declared)


@pytest.mark.parametrize(
    "identity",
    [
        "",
        " ",
        "0" * 63,
        "0" * 65,
        "g" * 64,
        None,
        1,
    ],
)
def test_invalid_observer_identity_fails_closed(identity):
    with pytest.raises(
        CompressionObserverCoverageError,
        match="sha256 identity",
    ):
        evaluate_compression_observer_coverage(
            required_observations=["value"],
            declared_observers=["value"],
            observer_identities={"value": identity},
            requirement_basis_ref="verification-contract:1",
        )


def test_uppercase_sha256_identity_is_canonicalized():
    identity = _identities(["value"])["value"].upper()

    receipt = evaluate_compression_observer_coverage(
        required_observations=["value"],
        declared_observers=["value"],
        observer_identities={"value": identity},
        requirement_basis_ref="verification-contract:1",
    )

    assert receipt["observer_identities"]["value"] == identity.lower()


@pytest.mark.parametrize("basis", ["", " ", None, 1])
def test_invalid_requirement_basis_fails_closed(basis):
    with pytest.raises(CompressionObserverCoverageError):
        evaluate_compression_observer_coverage(
            required_observations=["value"],
            declared_observers=["value"],
            observer_identities=_identities(["value"]),
            requirement_basis_ref=basis,
        )