import pytest

from holosim.core import HoloChain


def test_revalidation_receipt_cannot_be_corrected(tmp_path):
    chain = HoloChain(tmp_path / "receipt.jsonl")

    original = chain.append({"claim": "Original"})
    receipt = chain.revalidate(
        original["idx"],
        "HELD",
        "Test evidence",
        "Test method",
    )

    before = len(chain.load_and_verify())

    with pytest.raises(ValueError):
        chain.correct(
            receipt["idx"],
            {"claim": "Replacement"},
            "Receipts are not original claims",
        )

    assert len(chain.load_and_verify()) == before


def test_stored_correction_cannot_target_revalidation_receipt(tmp_path):
    chain = HoloChain(tmp_path / "stored.jsonl")

    original = chain.append({"claim": "Original"})
    receipt = chain.revalidate(
        original["idx"],
        "HELD",
        "Test evidence",
        "Test method",
    )

    chain.append({
        "_holo_record_type": "holo_correction",
        "version": 1,
        "corrects_idx": receipt["idx"],
        "corrects_hash": receipt["hash"],
        "reason": "Attempted receipt correction",
        "replacement": {"claim": "Replacement"},
    })

    with pytest.raises(ValueError):
        chain.get_effective_state()
