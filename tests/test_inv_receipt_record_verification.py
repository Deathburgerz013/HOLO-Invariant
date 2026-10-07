import json

import pytest

from holosim.inv_receipt_encoding import encode_receipt
from holosim.inv_receipt_identity import receipt_content_id
from holosim.inv_receipt_record import (
    BoundReceiptRecord,
    bind_receipt_bytes,
)
from holosim.inv_receipt_record_encoding import (
    encode_bound_receipt_record,
)
from holosim.inv_receipt_record_identity import (
    bound_receipt_record_content_id,
)
from holosim.inv_receipt_record_verification import (
    INVReceiptRecordVerificationError,
    verify_canonical_bound_receipt_record,
)
from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    SubtractTransition,
    TransitionDecisionReceipt,
    execute_inv_transition_with_receipt,
)


def make_receipt():
    return execute_inv_transition_with_receipt(
        state=5,
        transition=SubtractTransition(amount=6),
        invariant=GreaterThanOrEqualInvariant(minimum=0),
    )


def make_record():
    return bind_receipt_bytes(encode_receipt(make_receipt()))


def make_encoded_record():
    return encode_bound_receipt_record(make_record())


def test_complete_verification_returns_verified_receipt():
    encoded = make_encoded_record()
    outer_id = bound_receipt_record_content_id(encoded)

    receipt = verify_canonical_bound_receipt_record(
        encoded,
        outer_id,
    )

    assert receipt == make_receipt()


def test_outer_identity_mismatch_fails_closed():
    encoded = make_encoded_record()
    outer_id = bound_receipt_record_content_id(encoded)

    changed_outer_id = (
        ("0" if outer_id[0] != "0" else "1")
        + outer_id[1:]
    )

    with pytest.raises(
        INVReceiptRecordVerificationError,
        match="outer content identity mismatch",
    ):
        verify_canonical_bound_receipt_record(
            encoded,
            changed_outer_id,
        )


def test_malformed_outer_identity_fails_closed():
    encoded = make_encoded_record()

    with pytest.raises(
        INVReceiptRecordVerificationError,
        match="invalid outer content identity input",
    ):
        verify_canonical_bound_receipt_record(
            encoded,
            "not-an-id",
        )


def test_valid_outer_identity_does_not_validate_noncanonical_record():
    record = make_record()
    canonical = encode_bound_receipt_record(record)

    data = json.loads(canonical.decode("utf-8"))
    noncanonical = json.dumps(
        data,
        sort_keys=False,
        indent=2,
    ).encode("utf-8")

    outer_id = bound_receipt_record_content_id(noncanonical)

    with pytest.raises(
        INVReceiptRecordVerificationError,
        match="invalid canonical bound receipt record",
    ):
        verify_canonical_bound_receipt_record(
            noncanonical,
            outer_id,
        )


def test_valid_outer_identity_does_not_validate_malformed_record():
    malformed = b"not-json"
    outer_id = bound_receipt_record_content_id(malformed)

    with pytest.raises(
        INVReceiptRecordVerificationError,
        match="invalid canonical bound receipt record",
    ):
        verify_canonical_bound_receipt_record(
            malformed,
            outer_id,
        )


def test_valid_outer_identity_does_not_validate_inner_binding():
    record = make_record()
    invalid_inner = BoundReceiptRecord(
        encoded_receipt=record.encoded_receipt,
        content_id="0" * 64,
    )

    encoded = encode_bound_receipt_record(invalid_inner)
    outer_id = bound_receipt_record_content_id(encoded)

    with pytest.raises(
        INVReceiptRecordVerificationError,
        match="inner content binding mismatch",
    ):
        verify_canonical_bound_receipt_record(
            encoded,
            outer_id,
        )


def test_valid_outer_identity_and_inner_binding_do_not_validate_semantics():
    valid = make_receipt()

    contradictory = TransitionDecisionReceipt(
        previous_state=valid.previous_state,
        transition=valid.transition,
        candidate_state=valid.candidate_state,
        invariant=valid.invariant,
        accepted=True,
        resulting_state=valid.candidate_state,
    )

    encoded_receipt = encode_receipt(contradictory)

    record = BoundReceiptRecord(
        encoded_receipt=encoded_receipt,
        content_id=receipt_content_id(encoded_receipt),
    )

    encoded_record = encode_bound_receipt_record(record)
    outer_id = bound_receipt_record_content_id(encoded_record)

    with pytest.raises(
        INVReceiptRecordVerificationError,
        match="transition receipt semantic contradiction",
    ):
        verify_canonical_bound_receipt_record(
            encoded_record,
            outer_id,
        )


@pytest.mark.parametrize(
    "encoded",
    [
        None,
        "not-bytes",
        bytearray(b"record"),
    ],
)
def test_unsupported_outer_record_input_fails_closed(encoded):
    with pytest.raises(INVReceiptRecordVerificationError):
        verify_canonical_bound_receipt_record(
            encoded,
            "0" * 64,
        )
