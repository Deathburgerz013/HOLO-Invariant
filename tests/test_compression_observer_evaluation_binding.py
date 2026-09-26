from copy import deepcopy

import pytest

from holosim.bounded_python_callable_identity import (
    derive_python_callable_identity,
)
from holosim.bounded_repository_compression_evaluator import (
    EQUIVALENT,
    build_evaluation_scope,
    verify_compression_receipt,
)
from holosim.compression_observer_coverage import (
    evaluate_compression_observer_coverage,
)
from holosim.compression_observer_evaluation_binding import (
    CompressionObserverEvaluationBindingError,
    evaluate_bound_repository_compression,
)
from holosim.compression_observer_runtime_binding import (
    bind_compression_observer_runtime,
)


def value_observer(context, block):
    return block["value"]


def authority_observer(context, block):
    return {
        "authority": block["authority"],
        "platform": context["platform"],
    }


def substituted_value_observer(context, block):
    return block["authority"]


def _identity(function):
    return derive_python_callable_identity(function)[
        "callable_identity"
    ]


def _observers():
    return {
        "authority": authority_observer,
        "value": value_observer,
    }


def _coverage(observers=None):
    if observers is None:
        observers = _observers()

    names = sorted(observers)

    return evaluate_compression_observer_coverage(
        required_observations=names,
        declared_observers=names,
        observer_identities={
            name: _identity(observers[name])
            for name in names
        },
        requirement_basis_ref="verification-contract:compression-evaluation",
    )


def _binding(coverage=None, observers=None):
    if observers is None:
        observers = _observers()

    if coverage is None:
        coverage = _coverage(observers)

    return bind_compression_observer_runtime(
        coverage_receipt=coverage,
        observers=observers,
    )


def _scope():
    return build_evaluation_scope(
        observer_family_id="observers:compression-contract",
        observer_family={"observers": ["value", "authority"]},
        context_set_id="contexts:deterministic-v1",
        context_set={"contexts": ["default"]},
        compression_id="compression:remove-padding",
        compression_contract={
            "version": 1,
            "operation": "remove padding",
        },
        reconstruction_id="reconstruction:restore-shape",
        reconstruction_contract={
            "version": 1,
            "operation": "restore shape",
        },
        block_encoder_id="holo_canonical_json:1",
        block_encoder_contract={
            "encoding": "canonical-json",
            "version": 1,
        },
        representation_encoder_id="holo_canonical_json:1",
        representation_encoder_contract={
            "encoding": "canonical-json",
            "version": 1,
        },
        platform_id="test-platform",
        platform_contract={
            "python": "declared-test-runtime",
        },
        effect_runner_id="runner:captured-effects-v1",
        effect_runner_contract={
            "external_effects": "blocked",
            "effect_ledger": "required-empty",
        },
        determinism={
            "seed": 7,
            "clock": "fixed",
            "scheduler": "single-threaded",
            "trials": 1,
            "normalization": "exact-json",
        },
    )


def _baseline():
    return {
        "value": 7,
        "authority": "NONE",
        "padding": "x" * 200,
    }


def _compress(block):
    return {
        "value": block["value"],
        "authority": block["authority"],
    }


def _reconstruct(representation):
    return {
        **representation,
        "padding": "x" * 200,
    }


def _contexts():
    return {
        "default": {
            "platform": "test-platform",
            "effects": "captured",
        }
    }


def _effect_runner(operation, function, *arguments):
    return {
        "status": "COMPLETED",
        "value": function(*arguments),
        "effects": [],
        "external_effects_blocked": True,
    }


def _evaluate(**overrides):
    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    arguments = {
        "binding_receipt": binding,
        "coverage_receipt": coverage,
        "baseline": _baseline(),
        "compress": _compress,
        "reconstruct": _reconstruct,
        "observers": observers,
        "contexts": _contexts(),
        "rounds": 3,
        "scope": _scope(),
        "effect_runner": _effect_runner,
    }
    arguments.update(overrides)

    return evaluate_bound_repository_compression(**arguments)


def test_bound_observers_can_reach_compression_evaluator():
    receipt = _evaluate()

    assert receipt["result"] == EQUIVALENT
    assert receipt["reason"] is None
    assert len(receipt["rounds"]) == 3
    assert verify_compression_receipt(receipt)["valid"] is True


def test_bound_evaluation_preserves_evaluator_authority_boundary():
    receipt = _evaluate()

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_substituted_observer_is_blocked_before_evaluation():
    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["value"] = substituted_value_observer

    with pytest.raises(
        CompressionObserverEvaluationBindingError,
        match="observer binding must verify",
    ):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
        )


def test_forged_binding_receipt_is_blocked():
    observers = _observers()
    coverage = _coverage(observers)
    binding = deepcopy(_binding(coverage, observers))
    binding["status"] = "IDENTITY_MISMATCH"

    with pytest.raises(
        CompressionObserverEvaluationBindingError,
        match="observer binding must verify",
    ):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=observers,
        )


def test_valid_identity_mismatch_receipt_is_blocked():
    declared = _observers()
    coverage = _coverage(declared)

    runtime = dict(declared)
    runtime["value"] = substituted_value_observer

    mismatch_binding = _binding(
        coverage=coverage,
        observers=runtime,
    )

    assert mismatch_binding["status"] == "IDENTITY_MISMATCH"
    assert mismatch_binding["binding_complete"] is False

    with pytest.raises(
        CompressionObserverEvaluationBindingError,
        match="observer binding must be complete",
    ):
        _evaluate(
            binding_receipt=mismatch_binding,
            coverage_receipt=coverage,
            observers=runtime,
        )


def test_missing_runtime_observer_is_blocked():
    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    del runtime["value"]

    with pytest.raises(
        CompressionObserverEvaluationBindingError,
        match="observer binding must verify",
    ):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
        )


def test_extra_runtime_observer_is_blocked():
    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["extra"] = value_observer

    with pytest.raises(
        CompressionObserverEvaluationBindingError,
        match="observer binding must verify",
    ):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
        )


def test_changed_coverage_receipt_is_blocked():
    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    changed_coverage = evaluate_compression_observer_coverage(
        required_observations=sorted(observers),
        declared_observers=sorted(observers),
        observer_identities={
            name: _identity(observers[name])
            for name in sorted(observers)
        },
        requirement_basis_ref="verification-contract:different",
    )

    with pytest.raises(
        CompressionObserverEvaluationBindingError,
        match="observer binding must verify",
    ):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=changed_coverage,
            observers=observers,
        )


def test_binding_failure_prevents_compress_execution():
    calls = []

    def tracking_compress(block):
        calls.append("compress")
        return _compress(block)

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["value"] = substituted_value_observer

    with pytest.raises(CompressionObserverEvaluationBindingError):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
            compress=tracking_compress,
        )

    assert calls == []


def test_binding_failure_prevents_reconstruct_execution():
    calls = []

    def tracking_reconstruct(representation):
        calls.append("reconstruct")
        return _reconstruct(representation)

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["value"] = substituted_value_observer

    with pytest.raises(CompressionObserverEvaluationBindingError):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
            reconstruct=tracking_reconstruct,
        )

    assert calls == []


def test_binding_failure_prevents_effect_runner_execution():
    calls = []

    def tracking_effect_runner(operation, function, *arguments):
        calls.append(operation)
        return _effect_runner(operation, function, *arguments)

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["value"] = substituted_value_observer

    with pytest.raises(CompressionObserverEvaluationBindingError):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
            effect_runner=tracking_effect_runner,
        )

    assert calls == []


def test_binding_failure_prevents_observer_execution():
    calls = []

    def tracking_substituted_observer(context, block):
        calls.append((context, block))
        return block["authority"]

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["value"] = tracking_substituted_observer

    with pytest.raises(CompressionObserverEvaluationBindingError):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
        )

    assert calls == []


def test_binding_failure_prevents_every_downstream_operation():
    calls = []

    def tracking_compress(block):
        calls.append("compress")
        return _compress(block)

    def tracking_reconstruct(representation):
        calls.append("reconstruct")
        return _reconstruct(representation)

    def tracking_effect_runner(operation, function, *arguments):
        calls.append("effect_runner")
        return _effect_runner(operation, function, *arguments)

    def tracking_substituted_observer(context, block):
        calls.append("observer")
        return block["authority"]

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    runtime = dict(observers)
    runtime["value"] = tracking_substituted_observer

    with pytest.raises(CompressionObserverEvaluationBindingError):
        _evaluate(
            binding_receipt=binding,
            coverage_receipt=coverage,
            observers=runtime,
            compress=tracking_compress,
            reconstruct=tracking_reconstruct,
            effect_runner=tracking_effect_runner,
        )

    assert calls == []