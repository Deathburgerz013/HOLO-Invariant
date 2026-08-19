from copy import deepcopy

import pytest

from holosim.environment_invariant_receipts import (
    evaluate_environment_invariant,
)
from holosim.guarantee_environment_binding import (
    GuaranteeEnvironmentBindingError,
    bind_guarantee_environment,
    verify_guarantee_environment_binding,
)
from holosim.guarantee_registry import build_guarantee_registry


ENVIRONMENT = {
    "implementation": "CPython",
    "platform": "win32",
    "python": "3.13.7",
}

GUARANTEE = {
    "guarantee_id": "canonical-json-integrity",
    "guarantee_type": "integrity",
    "scope": "holosim.canonical_json",
    "dependencies": [
        "canonical JSON encoding",
        "SHA-256",
    ],
    "validator": "canonical-json-order-independence",
    "failure_condition": (
        "equivalent mappings produce different canonical encodings"
    ),
    "evidence": [
        "holosim/environment_invariant_receipts.py",
        "tests/test_environment_invariant_receipts.py",
    ],
}


def build_receipt(
    result=True,
    *,
    invariant_id="canonical-json-integrity",
    target="holosim.canonical_json",
    check_id="canonical-json-order-independence",
    sources=None,
):
    if sources is None:
        sources = GUARANTEE["evidence"]

    return evaluate_environment_invariant(
        invariant_id=invariant_id,
        statement=(
            "Equivalent mappings produce identical canonical encodings."
        ),
        scope={
            "target": target,
            "conditions": [
                "declared local environment",
            ],
        },
        environment=ENVIRONMENT,
        environment_probe=lambda: ENVIRONMENT,
        check_id=check_id,
        check=lambda: result,
        observed_at="2026-08-19T20:00:00Z",
        evidence={
            "sources": sources,
            "left": '{"a":1,"b":2}',
            "right": '{"a":1,"b":2}',
        },
    )


def bind(receipt):
    registry = build_guarantee_registry([GUARANTEE])
    return bind_guarantee_environment(
        registry=registry,
        receipt=receipt,
    )


def test_held_receipt_binds_registered_guarantee():
    receipt = build_receipt()

    binding = bind(receipt)

    assert binding["type"] == "holo_guarantee_environment_binding"
    assert binding["version"] == 1
    assert binding["status"] == "BOUND"
    assert binding["reason"] == "REGISTERED_CHECK_HELD"
    assert binding["guarantee_id"] == GUARANTEE["guarantee_id"]
    assert binding["registry_hash"]
    assert binding["receipt_hash"] == receipt["receipt_hash"]
    assert binding["environment_fingerprint"] == receipt[
        "environment_fingerprint"
    ]

    assert binding["accepted"] is False
    assert binding["truth_claimed"] is False
    assert binding["write_authority"] == "NONE"
    assert binding["execution_authority"] == "NONE"
    assert binding["canonical_mutation"] is False
    assert verify_guarantee_environment_binding(binding) is True


@pytest.mark.parametrize(
    ("receipt", "reason"),
    [
        (
            build_receipt(invariant_id="different-guarantee"),
            "GUARANTEE_ID_MISMATCH",
        ),
        (
            build_receipt(check_id="different-validator"),
            "VALIDATOR_MISMATCH",
        ),
        (
            build_receipt(target="different.scope"),
            "SCOPE_MISMATCH",
        ),
        (
            build_receipt(sources=["different-evidence.py"]),
            "EVIDENCE_MISMATCH",
        ),
    ],
)
def test_registration_mismatch_does_not_bind(
    receipt,
    reason,
):
    binding = bind(receipt)

    assert binding["status"] == "MISMATCH"
    assert binding["reason"] == reason
    assert binding["accepted"] is False
    assert binding["truth_claimed"] is False
    assert verify_guarantee_environment_binding(binding) is True


@pytest.mark.parametrize(
    ("result", "status", "reason"),
    [
        (
            False,
            "FAILED",
            "REGISTERED_CHECK_FAILED",
        ),
        (
            None,
            "UNKNOWN",
            "REGISTERED_CHECK_UNKNOWN",
        ),
    ],
)
def test_registered_nonheld_result_is_preserved(
    result,
    status,
    reason,
):
    binding = bind(build_receipt(result))

    assert binding["status"] == status
    assert binding["reason"] == reason
    assert verify_guarantee_environment_binding(binding) is True


def test_invalid_registry_hash_is_rejected():
    registry = build_guarantee_registry([GUARANTEE])
    registry["guarantees"][0]["validator"] = "forged-validator"

    with pytest.raises(
        GuaranteeEnvironmentBindingError,
        match="registry hash mismatch",
    ):
        bind_guarantee_environment(
            registry=registry,
            receipt=build_receipt(),
        )


def test_binding_is_deterministic():
    receipt = build_receipt()
    first = bind(receipt)
    second = bind(receipt)

    assert first == second
    assert first["binding_hash"] == second["binding_hash"]


def test_tampered_binding_is_rejected():
    binding = bind(build_receipt())
    tampered = deepcopy(binding)
    tampered["status"] = "MISMATCH"

    with pytest.raises(
        GuaranteeEnvironmentBindingError,
        match="binding hash mismatch",
    ):
        verify_guarantee_environment_binding(tampered)