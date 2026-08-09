from copy import deepcopy

import pytest

from holosim.bounded_repository_compression_evaluator import (
    DISTINCTION_LOST,
    EQUIVALENT,
    NOT_SIZE_REDUCING,
    UNKNOWN,
    BoundedRepositoryCompressionError,
    build_evaluation_scope,
    evaluate_repository_compression,
    verify_compression_receipt,
)
from holosim.canonical import stable_hash


def _scope():
    return build_evaluation_scope(
        observer_family_id="observers:compression-contract",
        observer_family={"observers": ["value", "authority"]},
        context_set_id="contexts:deterministic-v1",
        context_set={"contexts": ["default"]},
        compression_id="compression:remove-padding",
        compression_contract={"version": 1, "operation": "remove padding"},
        reconstruction_id="reconstruction:restore-shape",
        reconstruction_contract={"version": 1, "operation": "restore shape"},
        block_encoder_id="holo_canonical_json:1",
        block_encoder_contract={"encoding": "canonical-json", "version": 1},
        representation_encoder_id="holo_canonical_json:1",
        representation_encoder_contract={
            "encoding": "canonical-json",
            "version": 1,
        },
        platform_id="test-platform",
        platform_contract={"python": "declared-test-runtime"},
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


def _observers():
    return {
        "authority": lambda context, block: {
            "authority": block["authority"],
            "platform": context["platform"],
        },
        "value": lambda context, block: block["value"],
    }


def _contexts():
    return {"default": {"platform": "test-platform", "effects": "captured"}}


def _evaluate(**overrides):
    arguments = {
        "baseline": _baseline(),
        "compress": _compress,
        "reconstruct": _reconstruct,
        "observers": _observers(),
        "contexts": _contexts(),
        "rounds": 3,
        "scope": _scope(),
    }
    arguments.update(overrides)
    return evaluate_repository_compression(**arguments)


def _rehash(receipt):
    receipt["receipt_id"] = stable_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_id"
        }
    )


def test_repeated_size_reducing_rounds_are_bounded_equivalent():
    receipt = _evaluate()

    assert receipt["result"] == EQUIVALENT
    assert receipt["reason"] is None
    assert len(receipt["rounds"]) == 3
    assert all(item["size_reducing"] for item in receipt["rounds"])
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert verify_compression_receipt(receipt)["valid"] is True


def test_changed_observation_is_distinction_lost_with_witness():
    def reconstruct(representation):
        return {
            **representation,
            "value": representation["value"] + 1,
            "padding": "x" * 200,
        }

    receipt = _evaluate(reconstruct=reconstruct)

    assert receipt["result"] == DISTINCTION_LOST
    assert receipt["mismatch_witness"]["observer_id"] == "value"
    assert receipt["mismatch_witness"]["round"] == 1
    assert verify_compression_receipt(receipt)["valid"] is True


def test_authority_change_is_distinction_lost():
    def reconstruct(representation):
        return {
            **representation,
            "authority": "GRANTED",
            "padding": "x" * 200,
        }

    receipt = _evaluate(reconstruct=reconstruct)

    assert receipt["result"] == DISTINCTION_LOST
    assert receipt["mismatch_witness"]["observer_id"] == "authority"


def test_non_reducing_candidate_is_unknown_not_distinction_lost():
    receipt = _evaluate(compress=lambda block: deepcopy(block))

    assert receipt["result"] == UNKNOWN
    assert receipt["reason"] == NOT_SIZE_REDUCING
    assert receipt["mismatch_witness"] is None
    assert verify_compression_receipt(receipt)["valid"] is True


def test_observer_failure_is_unknown():
    def broken_observer(context, block):
        raise RuntimeError("observer unavailable")

    receipt = _evaluate(observers={"broken": broken_observer})

    assert receipt["result"] == UNKNOWN
    assert receipt["reason"] == "EVALUATION_ERROR:RuntimeError"
    assert verify_compression_receipt(receipt)["valid"] is True


def test_evaluation_does_not_mutate_supplied_data():
    baseline = _baseline()
    contexts = _contexts()
    before = deepcopy((baseline, contexts))

    _evaluate(baseline=baseline, contexts=contexts)

    assert (baseline, contexts) == before


def test_rounds_are_bounded():
    with pytest.raises(
        BoundedRepositoryCompressionError,
        match="rounds must be an integer",
    ):
        _evaluate(rounds=0)


def test_scope_rejects_undeclared_field():
    scope = _scope()
    scope["approval"] = "GRANTED"

    with pytest.raises(
        BoundedRepositoryCompressionError,
        match="unsupported fields",
    ):
        _evaluate(scope=scope)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("result", EQUIVALENT),
    ],
)
def test_rehashed_receipt_tampering_is_rejected(field, value):
    receipt = _evaluate(reconstruct=lambda value: {
        **value,
        "value": value["value"] + 1,
        "padding": "x" * 200,
    })
    receipt[field] = value
    _rehash(receipt)

    result = verify_compression_receipt(receipt)

    assert result["valid"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_rehashed_undeclared_receipt_field_is_rejected():
    receipt = _evaluate()
    receipt["approval"] = "GRANTED"
    _rehash(receipt)

    result = verify_compression_receipt(receipt)

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]


def test_rehashed_forged_equivalent_vector_is_rejected():
    receipt = _evaluate()
    receipt["rounds"][0]["observation_vector"][0]["observation"] = {
        "authority": "GRANTED",
        "platform": "test-platform",
    }
    _rehash(receipt)

    result = verify_compression_receipt(receipt)

    assert result["valid"] is False
    assert "observation mismatch" in result["violations"][0]


def test_rehashed_mismatch_witness_must_match_round_evidence():
    receipt = _evaluate(reconstruct=lambda value: {
        **value,
        "value": value["value"] + 1,
        "padding": "x" * 200,
    })
    receipt["mismatch_witness"]["candidate_observation"] = 999
    _rehash(receipt)

    result = verify_compression_receipt(receipt)

    assert result["valid"] is False
    assert "does not match recorded observations" in result["violations"][0]
