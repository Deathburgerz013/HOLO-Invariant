import hashlib
from dataclasses import replace

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_record import bind_receipt_bytes
from holosim.inv_receipt_record_encoding import encode_bound_receipt_record
from holosim.inv_receipt_record_identity import bound_receipt_record_content_id
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    ReplaceTransition,
    TransitionDecisionReceipt,
)
from holosim.inv_verification_receipt import (
    build_bound_verification_receipt,
    verify_bound_verification_receipt,
)
from holosim.inv_verification_receipt_encoding import (
    decode_bound_verification_receipt,
    encode_bound_verification_receipt,
)
from holosim.inv_verification_receipt_record import (
    BoundVerificationReceiptRecord,
    bind_verification_receipt_bytes,
    verify_bound_verification_receipt_record,
)
from holosim.inv_verification_receipt_record_encoding import (
    encode_bound_verification_receipt_record,
)
from holosim.inv_verification_receipt_record_identity import (
    INVVerificationReceiptRecordIdentityError,
    bound_verification_receipt_record_content_id,
    verify_bound_verification_receipt_record_content_id,
)


def make_verification_receipt():
    transition = TransitionDecisionReceipt(
        previous_state=5,
        transition=ReplaceTransition(value=4),
        candidate_state=4,
        invariant=GreaterThanOrEqualInvariant(minimum=0),
        accepted=True,
        resulting_state=4,
    )
    inner = bind_receipt_bytes(encode_receipt(transition))
    encoded_inner = encode_bound_receipt_record(inner)
    return build_bound_verification_receipt(
        encoded_inner,
        bound_receipt_record_content_id(encoded_inner),
    )


def make_record():
    return bind_verification_receipt_bytes(
        encode_bound_verification_receipt(make_verification_receipt())
    )


def test_exact_canonical_bytes_have_deterministic_sha256_identity():
    first = encode_bound_verification_receipt_record(make_record())
    second = encode_bound_verification_receipt_record(make_record())

    assert first == second
    assert bound_verification_receipt_record_content_id(first) == (
        hashlib.sha256(first).hexdigest()
    )
    assert bound_verification_receipt_record_content_id(first) == (
        bound_verification_receipt_record_content_id(second)
    )


def test_matching_identity_verifies_and_wrong_identity_does_not():
    encoded = encode_bound_verification_receipt_record(make_record())
    actual = bound_verification_receipt_record_content_id(encoded)
    wrong = ("0" if actual[0] != "0" else "1") + actual[1:]

    assert verify_bound_verification_receipt_record_content_id(
        encoded, actual
    ) is True
    assert verify_bound_verification_receipt_record_content_id(
        encoded, wrong
    ) is False


def test_outer_identity_covers_represented_inner_identifier():
    record = make_record()
    original = encode_bound_verification_receipt_record(record)
    changed_id = (
        ("0" if record.content_id[0] != "0" else "1")
        + record.content_id[1:]
    )
    changed = BoundVerificationReceiptRecord(
        encoded_verification_receipt=record.encoded_verification_receipt,
        content_id=changed_id,
    )
    changed_encoded = encode_bound_verification_receipt_record(changed)

    assert changed_encoded != original
    assert bound_verification_receipt_record_content_id(
        changed_encoded
    ) != bound_verification_receipt_record_content_id(original)
    assert verify_bound_verification_receipt_record(changed) is False
    assert verify_bound_verification_receipt_record_content_id(
        changed_encoded,
        bound_verification_receipt_record_content_id(changed_encoded),
    ) is True


def test_outer_identity_preserves_contradictory_embedded_evidence():
    contradictory = replace(
        make_verification_receipt(),
        semantic_verification_passed=False,
    )
    record = bind_verification_receipt_bytes(
        encode_bound_verification_receipt(contradictory)
    )
    encoded = encode_bound_verification_receipt_record(record)
    outer_id = bound_verification_receipt_record_content_id(encoded)

    assert verify_bound_verification_receipt_record_content_id(
        encoded, outer_id
    ) is True
    embedded = decode_bound_verification_receipt(
        record.encoded_verification_receipt
    )
    assert verify_bound_verification_receipt(embedded) is False


@pytest.mark.parametrize(
    "encoded",
    [None, "", bytearray(b"x"), memoryview(b"x")],
)
def test_unsupported_bytes_fail_closed(encoded):
    with pytest.raises(INVVerificationReceiptRecordIdentityError):
        bound_verification_receipt_record_content_id(encoded)


@pytest.mark.parametrize(
    "encoded",
    [b"", b"not-json", b"{}", b"[]", b"\xff"],
)
def test_noncanonical_bytes_fail_closed(encoded):
    with pytest.raises(INVVerificationReceiptRecordIdentityError):
        bound_verification_receipt_record_content_id(encoded)


@pytest.mark.parametrize(
    "expected",
    [None, b"0" * 64, "", "0" * 63, "0" * 65, "g" * 64],
)
def test_invalid_expected_identifiers_fail_closed(expected):
    encoded = encode_bound_verification_receipt_record(make_record())
    with pytest.raises(INVVerificationReceiptRecordIdentityError):
        verify_bound_verification_receipt_record_content_id(
            encoded, expected
        )


def test_uppercase_equivalent_expected_identifier_verifies():
    encoded = encode_bound_verification_receipt_record(make_record())
    actual = bound_verification_receipt_record_content_id(encoded)
    assert verify_bound_verification_receipt_record_content_id(
        encoded, actual.upper()
    ) is True

def test_changed_canonical_record_rejects_previous_outer_identity():
    record = make_record()
    original = encode_bound_verification_receipt_record(record)
    original_id = bound_verification_receipt_record_content_id(original)

    changed_inner_id = (
        ("0" if record.content_id[0] != "0" else "1")
        + record.content_id[1:]
    )
    changed = BoundVerificationReceiptRecord(
        encoded_verification_receipt=record.encoded_verification_receipt,
        content_id=changed_inner_id,
    )
    changed_encoded = encode_bound_verification_receipt_record(changed)

    assert verify_bound_verification_receipt_record_content_id(
        changed_encoded, original_id
    ) is False