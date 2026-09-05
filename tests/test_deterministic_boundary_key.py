from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.deterministic_boundary_key import (
    BoundaryKeyError,
    make_boundary_key_receipt,
    verify_boundary_key_receipt,
)


def descriptor(**changes):
    value = {
        "namespace": "holo",
        "subject_type": "receipt-boundary",
        "subject_id": "functional-awareness-loop",
        "scope": "holosim.functional_awareness_loop",
        "contract_type": "functional_awareness_loop_receipt",
        "contract_version": 1,
    }
    value.update(changes)
    return value


def test_same_descriptor_has_same_key_and_receipt() -> None:
    first = make_boundary_key_receipt(descriptor())
    second = make_boundary_key_receipt(dict(reversed(list(descriptor().items()))))
    assert first == second
    assert verify_boundary_key_receipt(first)["status"] == "PASS"


@pytest.mark.parametrize(
    "change",
    [
        {"namespace": "another"},
        {"subject_type": "claim-boundary"},
        {"subject_id": "another-loop"},
        {"scope": "holosim.other"},
        {"contract_type": "other_receipt"},
        {"contract_version": 2},
    ],
)
def test_meaningful_descriptor_change_has_different_key(change) -> None:
    baseline = make_boundary_key_receipt(descriptor())
    changed = make_boundary_key_receipt(descriptor(**change))
    assert baseline["boundary_key"] != changed["boundary_key"]


@pytest.mark.parametrize(
    "change",
    [
        {"namespace": ""},
        {"subject_id": "unknown subject"},
        {"scope": None},
        {"contract_version": 0},
        {"contract_version": True},
    ],
)
def test_ambiguous_or_invalid_identity_fails_closed(change) -> None:
    with pytest.raises(BoundaryKeyError):
        make_boundary_key_receipt(descriptor(**change))


def test_missing_or_extra_descriptor_field_fails_closed() -> None:
    missing = descriptor()
    missing.pop("scope")
    with pytest.raises(BoundaryKeyError, match="fields mismatch"):
        make_boundary_key_receipt(missing)
    with pytest.raises(BoundaryKeyError, match="fields mismatch"):
        make_boundary_key_receipt({**descriptor(), "claim": "true"})


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("boundary_key", "holo.boundary-key.v1:" + "0" * 64, "boundary_key_mismatch"),
        ("descriptor_hash", "0" * 64, "descriptor_hash_mismatch"),
        ("accepted", True, "forbidden_authority"),
        ("write_authority", "SELF", "forbidden_authority"),
    ],
)
def test_tampering_is_detected(field, value, failure) -> None:
    receipt = make_boundary_key_receipt(descriptor())
    receipt[field] = value
    result = verify_boundary_key_receipt(receipt)
    assert result["status"] == "FAIL"
    assert failure in result["failures"]
    assert "receipt_hash_mismatch" in result["failures"]


def test_rehashing_cannot_turn_authority_into_a_valid_key_receipt() -> None:
    from holosim.deterministic_boundary_key import _hash

    receipt = make_boundary_key_receipt(descriptor())
    receipt["accepted"] = True
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = _hash(body)
    result = verify_boundary_key_receipt(receipt)
    assert result["status"] == "FAIL"
    assert result["failures"] == ["forbidden_authority"]


def test_descriptor_substitution_is_detected() -> None:
    receipt = make_boundary_key_receipt(descriptor())
    receipt["descriptor"] = deepcopy(descriptor(scope="holosim.other"))
    result = verify_boundary_key_receipt(receipt)
    assert result["status"] == "FAIL"
    assert result["failures"] == [
        "descriptor_hash_mismatch",
        "boundary_key_mismatch",
        "receipt_hash_mismatch",
    ]


def test_receipt_never_claims_truth_or_authority() -> None:
    receipt = make_boundary_key_receipt(descriptor())
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert "truth" in receipt["interpretation_notice"]
    assert "authorship" in receipt["interpretation_notice"]
