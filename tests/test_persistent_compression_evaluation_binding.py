from holosim.authorized_baseline_transition import (
    authorize_baseline_transition,
    build_baseline_transition_candidate,
)
from holosim.baseline_observation_compare import (
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import evaluate_baseline_promotion
from holosim.bounded_baseline_content_identity import (
    bind_baseline_content_identity,
)
from holosim.bounded_python_callable_identity import (
    derive_python_callable_identity,
)
from holosim.bounded_repository_compression_evaluator import (
    EQUIVALENT,
    build_evaluation_scope,
)
from holosim.canonical import stable_hash
from holosim.compression_observer_coverage import (
    evaluate_compression_observer_coverage,
)
from holosim.compression_observer_runtime_binding import (
    bind_compression_observer_runtime,
)
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionStore,
)
from holosim.persistent_compression_evaluation_binding import (
    PersistentCompressionEvaluationBindingError,
    evaluate_current_persistent_repository_compression,
)
from holosim.typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    build_operational_authorization,
)


A_BASELINE = {
    "value": 7,
    "authority": "NONE",
    "padding": "x" * 200,
}

B_BASELINE = {
    "value": 8,
    "authority": "NONE",
    "padding": "x" * 200,
}

A_STATE = stable_hash(A_BASELINE)
B_STATE = stable_hash(B_BASELINE)


def stable_identity(value):
    return stable_hash(value)


def value_observer(context, block):
    return block["value"]


def authority_observer(context, block):
    return {
        "authority": block["authority"],
        "platform": context["platform"],
    }


def _identity(function):
    return derive_python_callable_identity(function)["callable_identity"]


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
        requirement_basis_ref=(
            "verification-contract:persistent-compression-evaluation"
        ),
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


def _store(tmp_path):
    return PersistentBaselineTransitionStore(
        tmp_path / "baseline-transitions.jsonl",
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )


def _content_receipt(
    baseline=A_BASELINE,
    *,
    baseline_id="baseline-a",
    state_identity=A_STATE,
):
    return bind_baseline_content_identity(
        baseline=baseline,
        baseline_id=baseline_id,
        declared_state_identity=state_identity,
        identity_function=stable_identity,
    )


def _authorized_transition():
    left = build_baseline_observation(
        observer_id="observer-a",
        baseline_id="baseline-a",
        baseline_state_hash=A_STATE,
        findings={"claim-a": "EXTENSION"},
    )
    right = build_baseline_observation(
        observer_id="observer-b",
        baseline_id="baseline-a",
        baseline_state_hash=A_STATE,
        findings={"claim-a": "EXTENSION"},
    )

    comparison = compare_baseline_observations(left, right)

    gate = evaluate_baseline_promotion(
        comparison=comparison,
        justification_references={
            "claim-a": "justification:claim-a:v1",
        },
    )

    candidate = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id="baseline-b",
        next_baseline_state_hash=B_STATE,
    )

    authorization = build_operational_authorization(
        authorization_id="approval:a-to-b",
        actor_id="external-reviewer",
        action=ACTION_BASELINE_PROMOTION,
        target_sha256=candidate["candidate_hash"],
        approval_reference="approval:a-to-b",
    )

    transition = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )

    return authorization, transition


def _advance_to_b(store):
    authorization, transition = _authorized_transition()
    store.commit(
        transition=transition,
        authorization=authorization,
    )


def _evaluate(tmp_path, **overrides):
    store = _store(tmp_path)
    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    arguments = {
        "store": store,
        "content_identity_receipt": _content_receipt(),
        "identity_function": stable_identity,
        "binding_receipt": binding,
        "coverage_receipt": coverage,
        "baseline": A_BASELINE,
        "compress": _compress,
        "reconstruct": _reconstruct,
        "observers": observers,
        "contexts": _contexts(),
        "rounds": 3,
        "scope": _scope(),
        "effect_runner": _effect_runner,
    }
    arguments.update(overrides)

    return evaluate_current_persistent_repository_compression(
        **arguments
    )


def test_current_persisted_baseline_reaches_compression_evaluation(
    tmp_path,
):
    result = _evaluate(tmp_path)

    assert result["result"] == EQUIVALENT
    assert len(result["rounds"]) == 3
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_stale_baseline_is_stopped_before_any_downstream_execution(
    tmp_path,
):
    store = _store(tmp_path)
    old_content_receipt = _content_receipt()
    _advance_to_b(store)

    calls = {
        "compress": 0,
        "reconstruct": 0,
        "observer": 0,
        "effect_runner": 0,
    }

    def exploding_compress(block):
        calls["compress"] += 1
        raise AssertionError("compress must not execute")

    def exploding_reconstruct(representation):
        calls["reconstruct"] += 1
        raise AssertionError("reconstruct must not execute")

    def exploding_effect_runner(operation, function, *arguments):
        calls["effect_runner"] += 1
        raise AssertionError("effect runner must not execute")

    observers = _observers()

    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    try:
        evaluate_current_persistent_repository_compression(
            store=store,
            content_identity_receipt=old_content_receipt,
            identity_function=stable_identity,
            binding_receipt=binding,
            coverage_receipt=coverage,
            baseline=A_BASELINE,
            compress=exploding_compress,
            reconstruct=exploding_reconstruct,
            observers=observers,
            contexts=_contexts(),
            rounds=1,
            scope=_scope(),
            effect_runner=exploding_effect_runner,
        )
    except PersistentCompressionEvaluationBindingError as exc:
        assert (
            str(exc)
            == "baseline content must be bound to the current persisted head"
        )
    else:
        raise AssertionError("stale baseline must fail closed")

    assert calls == {
        "compress": 0,
        "reconstruct": 0,
        "observer": 0,
        "effect_runner": 0,
    }


def test_substituted_compression_baseline_is_stopped_before_execution(
    tmp_path,
):
    store = _store(tmp_path)
    content_receipt = _content_receipt()

    calls = {
        "compress": 0,
        "reconstruct": 0,
        "observer": 0,
        "effect_runner": 0,
    }

    def exploding_compress(block):
        calls["compress"] += 1
        raise AssertionError("compress must not execute")

    def exploding_reconstruct(representation):
        calls["reconstruct"] += 1
        raise AssertionError("reconstruct must not execute")

    def exploding_effect_runner(operation, function, *arguments):
        calls["effect_runner"] += 1
        raise AssertionError("effect runner must not execute")

    observers = _observers()

    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    substituted = {
        **A_BASELINE,
        "value": 999,
    }

    try:
        evaluate_current_persistent_repository_compression(
            store=store,
            content_identity_receipt=content_receipt,
            identity_function=stable_identity,
            binding_receipt=binding,
            coverage_receipt=coverage,
            baseline=substituted,
            compress=exploding_compress,
            reconstruct=exploding_reconstruct,
            observers=observers,
            contexts=_contexts(),
            rounds=1,
            scope=_scope(),
            effect_runner=exploding_effect_runner,
        )
    except PersistentCompressionEvaluationBindingError as exc:
        assert (
            str(exc)
            == "compression baseline must exactly match bound baseline content"
        )
    else:
        raise AssertionError("substituted baseline must fail closed")

    assert calls == {
        "compress": 0,
        "reconstruct": 0,
        "observer": 0,
        "effect_runner": 0,
    }


def test_current_advanced_baseline_can_be_evaluated(tmp_path):
    store = _store(tmp_path)
    _advance_to_b(store)

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    result = evaluate_current_persistent_repository_compression(
        store=store,
        content_identity_receipt=_content_receipt(
            B_BASELINE,
            baseline_id="baseline-b",
            state_identity=B_STATE,
        ),
        identity_function=stable_identity,
        binding_receipt=binding,
        coverage_receipt=coverage,
        baseline=B_BASELINE,
        compress=_compress,
        reconstruct=_reconstruct,
        observers=observers,
        contexts=_contexts(),
        rounds=2,
        scope=_scope(),
        effect_runner=_effect_runner,
    )

    assert result["result"] == EQUIVALENT
    assert len(result["rounds"]) == 2


def test_restart_uses_reconstructed_current_head(tmp_path):
    path = tmp_path / "baseline-transitions.jsonl"

    first = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )
    _advance_to_b(first)

    restarted = PersistentBaselineTransitionStore(
        path,
        initial_baseline_id="baseline-a",
        initial_baseline_state_hash=A_STATE,
    )

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    result = evaluate_current_persistent_repository_compression(
        store=restarted,
        content_identity_receipt=_content_receipt(
            B_BASELINE,
            baseline_id="baseline-b",
            state_identity=B_STATE,
        ),
        identity_function=stable_identity,
        binding_receipt=binding,
        coverage_receipt=coverage,
        baseline=B_BASELINE,
        compress=_compress,
        reconstruct=_reconstruct,
        observers=observers,
        contexts=_contexts(),
        rounds=1,
        scope=_scope(),
        effect_runner=_effect_runner,
    )

    assert result["result"] == EQUIVALENT


def test_wrapper_does_not_add_authority(tmp_path):
    result = _evaluate(tmp_path)

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"

def test_stale_baseline_never_delegates_to_compression_evaluator(tmp_path, monkeypatch):
    store = _store(tmp_path)
    content_receipt = _content_receipt()
    _advance_to_b(store)

    calls = []

    def forbidden_delegate(**kwargs):
        calls.append(kwargs)
        raise AssertionError("compression evaluator must not be entered")

    monkeypatch.setattr(
        "holosim.persistent_compression_evaluation_binding.evaluate_bound_repository_compression",
        forbidden_delegate,
    )

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    try:
        evaluate_current_persistent_repository_compression(
            store=store,
            content_identity_receipt=content_receipt,
            identity_function=stable_identity,
            binding_receipt=binding,
            coverage_receipt=coverage,
            baseline=A_BASELINE,
            compress=_compress,
            reconstruct=_reconstruct,
            observers=observers,
            contexts=_contexts(),
            rounds=1,
            scope=_scope(),
            effect_runner=_effect_runner,
        )
    except PersistentCompressionEvaluationBindingError:
        pass
    else:
        raise AssertionError("stale baseline must fail closed")

    assert calls == []


def test_substituted_baseline_never_delegates_to_compression_evaluator(tmp_path, monkeypatch):
    store = _store(tmp_path)
    content_receipt = _content_receipt()

    calls = []

    def forbidden_delegate(**kwargs):
        calls.append(kwargs)
        raise AssertionError("compression evaluator must not be entered")

    monkeypatch.setattr(
        "holosim.persistent_compression_evaluation_binding.evaluate_bound_repository_compression",
        forbidden_delegate,
    )

    observers = _observers()
    coverage = _coverage(observers)
    binding = _binding(coverage, observers)

    substituted = {
        **A_BASELINE,
        "value": 999,
    }

    try:
        evaluate_current_persistent_repository_compression(
            store=store,
            content_identity_receipt=content_receipt,
            identity_function=stable_identity,
            binding_receipt=binding,
            coverage_receipt=coverage,
            baseline=substituted,
            compress=_compress,
            reconstruct=_reconstruct,
            observers=observers,
            contexts=_contexts(),
            rounds=1,
            scope=_scope(),
            effect_runner=_effect_runner,
        )
    except PersistentCompressionEvaluationBindingError:
        pass
    else:
        raise AssertionError("substituted baseline must fail closed")

    assert calls == []
