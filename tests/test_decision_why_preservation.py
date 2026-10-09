from copy import deepcopy

from holosim.bounded_repository_compression_evaluator import (
    DISTINCTION_LOST,
    EFFECT_RUNNER_REQUIRED,
    EQUIVALENT,
    UNKNOWN,
    build_evaluation_scope,
    evaluate_repository_compression,
    verify_compression_receipt,
)


WHY = "Allow future observers to challenge earlier conclusions."


def scope():
    return build_evaluation_scope(
        observer_family_id="observers:decision-why-v1",
        observer_family={"observers": ["decision_why"]},
        context_set_id="contexts:decision-why-v1",
        context_set={"contexts": ["default"]},
        compression_id="compression:decision-why-v1",
        compression_contract={
            "version": 1,
            "operation": "remove padding; optionally lose rationale",
        },
        reconstruction_id="reconstruction:decision-why-v1",
        reconstruction_contract={
            "version": 1,
            "operation": "restore padding; preserve supplied rationale",
        },
        block_encoder_id="holo_canonical_json:1",
        block_encoder_contract={"encoding": "canonical-json", "version": 1},
        representation_encoder_id="holo_canonical_json:1",
        representation_encoder_contract={
            "encoding": "canonical-json",
            "version": 1,
        },
        platform_id="test-platform",
        platform_contract={"python": "declared-test-runtime"},
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


def baseline():
    return {
        "decision": "Preserve the original correction record.",
        "decision_why": WHY,
        "padding": "x" * 200,
    }


def compress(block):
    return {
        key: deepcopy(value)
        for key, value in block.items()
        if key != "padding"
    }


def reconstruct(representation):
    return {**representation, "padding": "x" * 200}


def runner(operation, function, *arguments):
    return {
        "status": "COMPLETED",
        "value": function(*arguments),
        "effects": [],
        "external_effects_blocked": True,
    }


def evaluate(*, compressor=compress, effect_runner=runner):
    return evaluate_repository_compression(
        baseline=baseline(),
        compress=compressor,
        reconstruct=reconstruct,
        observers={
            "decision_why": lambda context, block: block.get(
                "decision_why", "MISSING"
            ),
        },
        contexts={"default": {"purpose": "rationale preservation"}},
        rounds=2,
        scope=scope(),
        effect_runner=effect_runner,
    )


def test_preserved_decision_why_is_bounded_equivalent():
    receipt = evaluate()
    assert receipt["result"] == EQUIVALENT
    assert receipt["accepted"] is False
    assert verify_compression_receipt(receipt)["valid"] is True


def test_removed_decision_why_is_distinction_lost():
    def lose_why(block):
        return {
            key: deepcopy(value)
            for key, value in block.items()
            if key not in {"padding", "decision_why"}
        }

    receipt = evaluate(compressor=lose_why)

    assert receipt["result"] == DISTINCTION_LOST
    assert receipt["mismatch_witness"]["observer_id"] == "decision_why"
    assert receipt["mismatch_witness"]["round"] == 1
    assert verify_compression_receipt(receipt)["valid"] is True


def test_unverified_execution_boundary_is_unknown():
    receipt = evaluate(effect_runner=None)

    assert receipt["result"] == UNKNOWN
    assert receipt["reason"] == EFFECT_RUNNER_REQUIRED
