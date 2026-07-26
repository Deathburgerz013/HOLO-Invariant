from __future__ import annotations

import pytest

from holosim.canonical import stable_hash
from holosim.correction import record_correction


PREVIOUS = "1" * 64
PROPOSED = "2" * 64
RESULTING = "3" * 64
EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64


def test_record_correction_preserves_transition_and_reason() -> None:
    metadata = {"module": "software_generator", "cycle": 2}

    receipt = record_correction(
        PREVIOUS,
        PROPOSED,
        RESULTING,
        "verification exposed an invalid assumption",
        [EVIDENCE_A, EVIDENCE_B],
        metadata=metadata,
    )

    assert receipt["type"] == "correction_receipt"
    assert receipt["version"] == 1
    assert receipt["previous_receipt_hash"] == PREVIOUS
    assert receipt["proposed_receipt_hash"] == PROPOSED
    assert receipt["resulting_receipt_hash"] == RESULTING
    assert receipt["reason"] == (
        "verification exposed an invalid assumption"
    )
    assert receipt["evidence_receipt_hashes"] == [
        EVIDENCE_A,
        EVIDENCE_B,
    ]
    assert receipt["metadata"] == metadata
    assert receipt["changed"] is True
    assert receipt["proposal_adopted"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    assert receipt["receipt_hash"] == stable_hash(body)


def test_rejection_can_preserve_previous_state_without_erasing_proposal() -> None:
    receipt = record_correction(
        PREVIOUS,
        PROPOSED,
        PREVIOUS,
        "proposal failed verification",
        [EVIDENCE_A],
    )

    assert receipt["changed"] is False
    assert receipt["proposal_adopted"] is False
    assert receipt["previous_receipt_hash"] == PREVIOUS
    assert receipt["proposed_receipt_hash"] == PROPOSED
    assert receipt["resulting_receipt_hash"] == PREVIOUS


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("previous", "not-a-hash"),
        ("proposed", "A" * 64),
        ("resulting", "3" * 63),
    ],
)
def test_receipt_hash_fields_must_be_lowercase_sha256(
    field: str,
    value: str,
) -> None:
    hashes = {
        "previous": PREVIOUS,
        "proposed": PROPOSED,
        "resulting": RESULTING,
    }
    hashes[field] = value

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        record_correction(
            hashes["previous"],
            hashes["proposed"],
            hashes["resulting"],
            "reason",
            [EVIDENCE_A],
        )


def test_correction_requires_reason_and_unique_evidence() -> None:
    with pytest.raises(ValueError, match="reason must be"):
        record_correction(
            PREVIOUS,
            PROPOSED,
            RESULTING,
            "   ",
            [EVIDENCE_A],
        )

    with pytest.raises(ValueError, match="at least one evidence"):
        record_correction(
            PREVIOUS,
            PROPOSED,
            RESULTING,
            "reason",
            [],
        )

    with pytest.raises(ValueError, match="must be unique"):
        record_correction(
            PREVIOUS,
            PROPOSED,
            RESULTING,
            "reason",
            [EVIDENCE_A, EVIDENCE_A],
        )
