from __future__ import annotations

import pytest

from holosim.canonical import stable_hash
from holosim.fact_identity import (
    VerifiedFactIdentityError,
    build_verified_fact_identity_receipt,
    verify_fact_identity_receipt,
)


def members():
    return [
        {
            "analysis_id": "model-b",
            "finding_id": "model-b.output-3",
        },
        {
            "analysis_id": "model-a",
            "finding_id": "model-a.fact-17",
        },
    ]


def test_build_and_verify_fact_identity_receipt() -> None:
    receipt = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=members(),
    )

    assert receipt["fact_id"] == "fact:x"
    assert receipt["members"] == [
        {
            "analysis_id": "model-a",
            "finding_id": "model-a.fact-17",
        },
        {
            "analysis_id": "model-b",
            "finding_id": "model-b.output-3",
        },
    ]
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert verify_fact_identity_receipt(receipt) is True


def test_fact_identity_receipt_is_deterministic() -> None:
    forward = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=members(),
    )
    reverse = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=list(reversed(members())),
    )

    assert forward == reverse


def test_duplicate_fact_identity_member_fails_closed() -> None:
    duplicate = [
        {
            "analysis_id": "model-a",
            "finding_id": "model-a.fact-17",
        },
        {
            "analysis_id": "model-a",
            "finding_id": "model-a.fact-17",
        },
    ]

    with pytest.raises(
        VerifiedFactIdentityError,
        match="duplicated",
    ):
        build_verified_fact_identity_receipt(
            fact_id="fact:x",
            members=duplicate,
        )


def test_fact_identity_receipt_hash_tampering_is_rejected() -> None:
    receipt = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=members(),
    )
    receipt["fact_id"] = "fact:y"

    with pytest.raises(
        VerifiedFactIdentityError,
        match="hash mismatch",
    ):
        verify_fact_identity_receipt(receipt)


def test_rehashed_fact_identity_authority_forgery_is_rejected() -> None:
    receipt = build_verified_fact_identity_receipt(
        fact_id="fact:x",
        members=members(),
    )
    receipt["accepted"] = True

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        VerifiedFactIdentityError,
        match="internally inconsistent",
    ):
        verify_fact_identity_receipt(receipt)
