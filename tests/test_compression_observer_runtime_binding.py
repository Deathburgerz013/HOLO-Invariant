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
    verify_compression_observer_runtime_binding_receipt,
)


def value_observer(value, context):
    return value["value"]


def authority_observer(value, context):
    return value["authority"]


def provenance_observer(value, context):
    return value["provenance"]


def different_value_observer(value, context):
    return value["authority"]


def exploding_observer(value, context):
    raise AssertionError("observer must not execute")


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


def _binding():
    coverage = _coverage()
    receipt = bind_compression_observer_runtime(
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )
    return coverage, receipt


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


def test_valid_binding_receipt_verifies():
    coverage, receipt = _binding()

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is True
    assert result["violations"] == []
    assert result["receipt_id"] == receipt["receipt_id"]
    assert result["expected_receipt_id"] == receipt["receipt_id"]


def test_forged_binding_status_is_rejected():
    coverage, receipt = _binding()
    forged = deepcopy(receipt)
    forged["status"] = "IDENTITY_MISMATCH"

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=forged,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert "status does not match replay" in result["violations"]


def test_forged_binding_complete_is_rejected():
    coverage, receipt = _binding()
    forged = deepcopy(receipt)
    forged["binding_complete"] = False

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=forged,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert "binding_complete does not match replay" in result["violations"]


def test_forged_runtime_identity_is_rejected():
    coverage, receipt = _binding()
    forged = deepcopy(receipt)
    forged["runtime_observer_identities"]["value"] = "0" * 64

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=forged,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert (
        "runtime_observer_identities does not match replay"
        in result["violations"]
    )


def test_forged_receipt_id_is_rejected():
    coverage, receipt = _binding()
    forged = deepcopy(receipt)
    forged["receipt_id"] = "0" * 64

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=forged,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert "receipt_id does not match replay" in result["violations"]
    assert result["expected_receipt_id"] == receipt["receipt_id"]


def test_extra_binding_receipt_field_is_rejected():
    coverage, receipt = _binding()
    forged = deepcopy(receipt)
    forged["invented"] = True

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=forged,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert "receipt fields do not match replay" in result["violations"]


def test_missing_binding_receipt_field_is_rejected():
    coverage, receipt = _binding()
    forged = deepcopy(receipt)
    del forged["status"]

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=forged,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert "receipt fields do not match replay" in result["violations"]


def test_runtime_observer_substitution_invalidates_bound_receipt():
    coverage, receipt = _binding()

    runtime = dict(OBSERVERS)
    runtime["value"] = different_value_observer

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=coverage,
        observers=runtime,
    )

    assert result["valid"] is False
    assert (
        "runtime_observer_identities does not match replay"
        in result["violations"]
    )
    assert "mismatched_observers does not match replay" in result["violations"]
    assert "binding_complete does not match replay" in result["violations"]
    assert "status does not match replay" in result["violations"]
    assert "receipt_id does not match replay" in result["violations"]


def test_different_coverage_receipt_invalidates_binding_receipt():
    coverage, receipt = _binding()

    names = sorted(OBSERVERS)
    other_coverage = evaluate_compression_observer_coverage(
        required_observations=names,
        declared_observers=names,
        observer_identities={
            name: _identity(OBSERVERS[name])
            for name in names
        },
        requirement_basis_ref="verification-contract:other",
    )

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=other_coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert "coverage_receipt_id does not match replay" in result["violations"]
    assert "requirement_basis_ref does not match replay" in result["violations"]
    assert "receipt_id does not match replay" in result["violations"]


def test_verifier_rejects_tampered_coverage_receipt():
    coverage, receipt = _binding()
    tampered = deepcopy(coverage)
    tampered["status"] = "COVERAGE_INCOMPLETE"

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=tampered,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is None
    assert any(
        "coverage_receipt must verify" in violation
        for violation in result["violations"]
    )


def test_verifier_rejects_missing_runtime_observer():
    coverage, receipt = _binding()
    runtime = dict(OBSERVERS)
    del runtime["value"]

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=coverage,
        observers=runtime,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is None
    assert any(
        "exactly match declared_observers" in violation
        for violation in result["violations"]
    )


def test_verifier_rejects_non_mapping_receipt():
    coverage = _coverage()

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=None,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["valid"] is False
    assert result["receipt_id"] is None
    assert result["expected_receipt_id"] is None
    assert "receipt must be a mapping" in result["violations"]


def test_verification_does_not_execute_observers():
    observers = {
        "value": exploding_observer,
    }

    coverage = evaluate_compression_observer_coverage(
        required_observations=["value"],
        declared_observers=["value"],
        observer_identities={
            "value": _identity(exploding_observer),
        },
        requirement_basis_ref="verification-contract:verify-no-execution",
    )

    receipt = bind_compression_observer_runtime(
        coverage_receipt=coverage,
        observers=observers,
    )

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=coverage,
        observers=observers,
    )

    assert result["valid"] is True
    assert result["observers_executed"] is False


def test_verification_grants_no_authority():
    coverage, receipt = _binding()

    result = verify_compression_observer_runtime_binding_receipt(
        receipt=receipt,
        coverage_receipt=coverage,
        observers=OBSERVERS,
    )

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"