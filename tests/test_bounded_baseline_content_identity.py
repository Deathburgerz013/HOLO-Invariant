from copy import deepcopy

import pytest

from holosim.bounded_baseline_content_identity import (
    BOUND,
    IDENTITY_FUNCTION_ERROR,
    IDENTITY_MISMATCH,
    BoundedBaselineContentIdentityError,
    bind_baseline_content_identity,
    verify_baseline_content_identity_receipt,
)
from holosim.canonical import stable_hash


BASELINE = {
    "claims": [
        {"id": "a", "value": 1},
        {"id": "b", "value": 2},
    ],
    "authority": "NONE",
}


def stable_identity(value):
    return stable_hash(value)


def different_identity(value):
    return "different:" + stable_hash(value)


def failing_identity(value):
    raise RuntimeError("identity failure")


def non_string_identity(value):
    return {"hash": stable_hash(value)}


def _receipt():
    return bind_baseline_content_identity(
        baseline=BASELINE,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(BASELINE),
        identity_function=stable_identity,
    )


def test_matching_content_identity_is_bound():
    receipt = _receipt()

    assert receipt["status"] == BOUND
    assert receipt["binding_complete"] is True
    assert receipt["declared_state_identity"] == stable_hash(BASELINE)
    assert receipt["observed_state_identity"] == stable_hash(BASELINE)


def test_receipt_contains_canonical_baseline():
    receipt = _receipt()

    assert receipt["baseline"] == BASELINE
    assert receipt["baseline"] is not BASELINE


def test_receipt_contains_identity_function_identity():
    receipt = _receipt()

    identity = receipt["identity_function_identity"]

    assert identity["type"] == "bounded_python_callable_identity"
    assert identity["version"] == 1
    assert len(identity["callable_identity"]) == 64


def test_matching_receipt_replays():
    receipt = _receipt()

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is True
    assert result["receipt_id"] == receipt["receipt_id"]
    assert result["expected_receipt_id"] == receipt["receipt_id"]
    assert result["violations"] == []


def test_different_content_produces_identity_mismatch():
    changed = deepcopy(BASELINE)
    changed["claims"][0]["value"] = 99

    receipt = bind_baseline_content_identity(
        baseline=changed,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(BASELINE),
        identity_function=stable_identity,
    )

    assert receipt["status"] == IDENTITY_MISMATCH
    assert receipt["binding_complete"] is False
    assert receipt["observed_state_identity"] == stable_hash(changed)


def test_identity_mismatch_receipt_can_still_verify():
    changed = deepcopy(BASELINE)
    changed["claims"][0]["value"] = 99

    receipt = bind_baseline_content_identity(
        baseline=changed,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(BASELINE),
        identity_function=stable_identity,
    )

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert receipt["status"] == IDENTITY_MISMATCH
    assert receipt["binding_complete"] is False
    assert result["valid"] is True


def test_different_identity_function_is_detected_on_replay():
    receipt = _receipt()

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=different_identity,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is None
    assert result["violations"] == [
        "identity_function does not match receipt identity"
    ]


def test_tampered_baseline_is_detected():
    receipt = deepcopy(_receipt())
    receipt["baseline"]["claims"][0]["value"] = 99

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is not None


def test_tampered_declared_identity_is_detected():
    receipt = deepcopy(_receipt())
    receipt["declared_state_identity"] = "0" * 64

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is not None


def test_tampered_observed_identity_is_detected():
    receipt = deepcopy(_receipt())
    receipt["observed_state_identity"] = "0" * 64

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False


def test_tampered_status_is_detected():
    receipt = deepcopy(_receipt())
    receipt["status"] = IDENTITY_MISMATCH

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False


def test_tampered_binding_complete_is_detected():
    receipt = deepcopy(_receipt())
    receipt["binding_complete"] = False

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False


def test_tampered_function_identity_is_detected():
    receipt = deepcopy(_receipt())
    receipt["identity_function_identity"]["callable_identity"] = "0" * 64

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is None


def test_tampered_receipt_id_is_detected():
    receipt = deepcopy(_receipt())
    receipt["receipt_id"] = "0" * 64

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] != result["receipt_id"]


def test_extra_receipt_field_is_detected():
    receipt = deepcopy(_receipt())
    receipt["extra"] = True

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False


def test_missing_receipt_field_is_detected():
    receipt = deepcopy(_receipt())
    del receipt["status"]

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=stable_identity,
    )

    assert result["valid"] is False


def test_non_mapping_receipt_fails_closed():
    result = verify_baseline_content_identity_receipt(
        None,
        identity_function=stable_identity,
    )

    assert result["valid"] is False
    assert result["expected_receipt_id"] is None
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_identity_function_exception_becomes_failure_receipt():
    receipt = bind_baseline_content_identity(
        baseline=BASELINE,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(BASELINE),
        identity_function=failing_identity,
    )

    assert receipt["status"] == IDENTITY_FUNCTION_ERROR
    assert receipt["binding_complete"] is False
    assert receipt["observed_state_identity"] is None


def test_identity_function_error_receipt_replays():
    receipt = bind_baseline_content_identity(
        baseline=BASELINE,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(BASELINE),
        identity_function=failing_identity,
    )

    result = verify_baseline_content_identity_receipt(
        receipt,
        identity_function=failing_identity,
    )

    assert result["valid"] is True


def test_non_string_identity_result_becomes_failure_receipt():
    receipt = bind_baseline_content_identity(
        baseline=BASELINE,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(BASELINE),
        identity_function=non_string_identity,
    )

    assert receipt["status"] == IDENTITY_FUNCTION_ERROR
    assert receipt["binding_complete"] is False
    assert receipt["observed_state_identity"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("baseline_id", ""),
        ("baseline_id", "   "),
        ("baseline_id", None),
        ("declared_state_identity", ""),
        ("declared_state_identity", "   "),
        ("declared_state_identity", None),
    ],
)
def test_invalid_text_inputs_fail_closed(field, value):
    arguments = {
        "baseline": BASELINE,
        "baseline_id": "baseline-1",
        "declared_state_identity": stable_hash(BASELINE),
        "identity_function": stable_identity,
    }
    arguments[field] = value

    with pytest.raises(BoundedBaselineContentIdentityError):
        bind_baseline_content_identity(**arguments)


def test_noncanonical_baseline_fails_closed():
    with pytest.raises(
        BoundedBaselineContentIdentityError,
        match="canonical JSON",
    ):
        bind_baseline_content_identity(
            baseline={"bad": {1, 2, 3}},
            baseline_id="baseline-1",
            declared_state_identity="state-1",
            identity_function=stable_identity,
        )


def test_closure_identity_function_fails_closed():
    prefix = "state:"

    def closed_identity(value):
        return prefix + stable_hash(value)

    with pytest.raises(
        BoundedBaselineContentIdentityError,
        match="unsupported identity",
    ):
        bind_baseline_content_identity(
            baseline=BASELINE,
            baseline_id="baseline-1",
            declared_state_identity=stable_hash(BASELINE),
            identity_function=closed_identity,
        )


def test_binding_does_not_mutate_baseline():
    baseline = deepcopy(BASELINE)
    original = deepcopy(baseline)

    bind_baseline_content_identity(
        baseline=baseline,
        baseline_id="baseline-1",
        declared_state_identity=stable_hash(baseline),
        identity_function=stable_identity,
    )

    assert baseline == original


def test_binding_grants_no_authority():
    receipt = _receipt()

    assert receipt["baseline_truth_verified"] is False
    assert receipt["baseline_current_verified"] is False
    assert receipt["persistence_verified"] is False
    assert receipt["compression_preservation_verified"] is False
    assert receipt["compression_authorized"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_binding_is_deterministic():
    first = _receipt()
    second = _receipt()

    assert first == second