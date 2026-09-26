from copy import deepcopy

import pytest

from holosim.bounded_python_callable_identity import (
    derive_python_callable_identity,
)
from holosim.compression_observer_coverage import (
    evaluate_compression_observer_coverage,
)
from holosim.compression_observer_runtime_binding import (
    CompressionObserverRuntimeBindingError,
    bind_compression_observer_runtime,
)


def value_observer(value, context):
    return value["value"]


def authority_observer(value, context):
    return value["authority"]


def provenance_observer(value, context):
    return value["provenance"]


def different_value_observer(value, context):
    return value["authority"]


OBSERVERS = {
    "authority": authority_observer,
    "provenance": provenance_observer,
    "value": value_observer,
}


def _identity(function):
    return derive_python_callable_identity(function)[
        "callable_identity"
    ]


def _coverage():
    names = sorted(OBSERVERS)

    return evaluate_compression_observer_coverage(
        required_observations=names,
        declared_observers=names,
        observer_identities={
            name: _identity(OBSERVERS[name])
            for name in names
        },
        requirement_basis_ref="verification-contract:1",
    )


def test_matching_runtime_observers_are_bound():
    receipt = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=OBSERVERS,
    )

    assert receipt["status"] == "BOUND"
    assert receipt["binding_complete"] is True
    assert receipt["mismatched_observers"] == []


def test_runtime_identities_match_declared_identities():
    receipt = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=OBSERVERS,
    )

    assert (
        receipt["runtime_observer_identities"]
        == receipt["declared_observer_identities"]
    )


def test_different_runtime_implementation_is_detected():
    runtime = dict(OBSERVERS)
    runtime["value"] = different_value_observer

    receipt = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=runtime,
    )

    assert receipt["status"] == "IDENTITY_MISMATCH"
    assert receipt["binding_complete"] is False
    assert receipt["mismatched_observers"] == ["value"]


def test_runtime_implementation_mismatch_changes_receipt_identity():
    bound = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=OBSERVERS,
    )

    runtime = dict(OBSERVERS)
    runtime["value"] = different_value_observer

    mismatch = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=runtime,
    )

    assert bound["receipt_id"] != mismatch["receipt_id"]


def test_missing_runtime_observer_fails_closed():
    runtime = dict(OBSERVERS)
    del runtime["provenance"]

    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="exactly match declared_observers",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=_coverage(),
            observers=runtime,
        )


def test_extra_runtime_observer_fails_closed():
    runtime = dict(OBSERVERS)
    runtime["extra"] = value_observer

    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="exactly match declared_observers",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=_coverage(),
            observers=runtime,
        )


def test_empty_runtime_observers_fail_closed():
    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="nonempty mapping",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=_coverage(),
            observers={},
        )


def test_non_mapping_runtime_observers_fail_closed():
    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="nonempty mapping",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=_coverage(),
            observers=["value"],
        )


def test_tampered_coverage_receipt_fails_before_binding():
    coverage = deepcopy(_coverage())
    coverage["observer_identities"]["value"] = "0" * 64

    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="must verify",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=coverage,
            observers=OBSERVERS,
        )


def test_tampered_coverage_status_fails_before_binding():
    coverage = deepcopy(_coverage())
    coverage["status"] = "COVERAGE_INCOMPLETE"

    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="must verify",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=coverage,
            observers=OBSERVERS,
        )


def test_non_mapping_coverage_receipt_fails_closed():
    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="coverage_receipt must be a mapping",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=None,
            observers=OBSERVERS,
        )


def test_closure_runtime_observer_fails_closed():
    offset = 1

    def closed_observer(value, context):
        return value["value"] + offset

    runtime = dict(OBSERVERS)
    runtime["value"] = closed_observer

    with pytest.raises(
        CompressionObserverRuntimeBindingError,
        match="unsupported identity",
    ):
        bind_compression_observer_runtime(
            coverage_receipt=_coverage(),
            observers=runtime,
        )


def test_binding_does_not_execute_observers():
    calls = []

    def tracking_observer(value, context):
        calls.append((value, context))
        return value["value"]

    observers = {
        "value": tracking_observer,
    }

    coverage = evaluate_compression_observer_coverage(
        required_observations=["value"],
        declared_observers=["value"],
        observer_identities={
            "value": _identity(tracking_observer),
        },
        requirement_basis_ref="verification-contract:tracking",
    )

    receipt = bind_compression_observer_runtime(
        coverage_receipt=coverage,
        observers=observers,
    )

    assert receipt["binding_complete"] is True
    assert receipt["observers_executed"] is False
    assert calls == []


def test_binding_grants_no_truth_or_compression_authority():
    receipt = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=OBSERVERS,
    )

    assert receipt["observers_executed"] is False
    assert receipt["observation_truth_verified"] is False
    assert receipt["compression_preservation_verified"] is False
    assert receipt["compression_authorized"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_binding_is_deterministic():
    first = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=OBSERVERS,
    )
    second = bind_compression_observer_runtime(
        coverage_receipt=_coverage(),
        observers=dict(reversed(list(OBSERVERS.items()))),
    )

    assert first == second
def test_binding_does_not_execute_observers():
    def exploding_observer(value, context):
        raise AssertionError("observer must not execute during binding")

    observers = {
        "value": exploding_observer,
    }

    coverage = evaluate_compression_observer_coverage(
        required_observations=["value"],
        declared_observers=["value"],
        observer_identities={
            "value": _identity(exploding_observer),
        },
        requirement_basis_ref="verification-contract:execution-absence",
    )

    receipt = bind_compression_observer_runtime(
        coverage_receipt=coverage,
        observers=observers,
    )

    assert receipt["binding_complete"] is True
    assert receipt["status"] == "BOUND"
    assert receipt["observers_executed"] is False