import pytest

from holosim.core import HoloChain


def test_correction_uses_verified_snapshot_for_target_classification(
    tmp_path, monkeypatch
):
    chain = HoloChain(tmp_path / "snapshot.jsonl")

    original = chain.append({"claim": "Original"})
    receipt = chain.revalidate(
        original["idx"],
        "HELD",
        "Test evidence",
        "Test method",
    )

    before = len(chain.load_and_verify())

    # Simulate a second read disagreeing with the verified entries.
    # The receipt is falsely represented as an ordinary claim.
    monkeypatch.setattr(
        chain,
        "get_state",
        lambda: [
            {"claim": "Original"},
            {"claim": "Forged classification"},
        ],
    )

    with pytest.raises(ValueError, match="original entry"):
        chain.correct(
            receipt["idx"],
            {"claim": "Unauthorized replacement"},
            "Attempt to correct a receipt",
        )

    assert len(chain.load_and_verify()) == before


def test_correction_rejects_invalid_existing_history(tmp_path):
    chain = HoloChain(tmp_path / "invalid_history.jsonl")

    original = chain.append({"claim": "Original"})
    operational = chain.append({
        "type": "service_append",
        "content": "Operational event",
    })

    chain.append({
        "_holo_record_type": "holo_correction",
        "version": 1,
        "corrects_idx": operational["idx"],
        "corrects_hash": operational["hash"],
        "reason": "Invalid operational correction",
        "replacement": {"claim": "Invalid"},
    })

    before = len(chain.load_and_verify())

    with pytest.raises(ValueError):
        chain.get_effective_state()

    with pytest.raises(ValueError):
        chain.correct(
            original["idx"],
            {"claim": "Replacement"},
            "Valid correction after invalid history",
        )

    assert len(chain.load_and_verify()) == before


def test_correction_rejects_intervening_invalid_history(tmp_path, monkeypatch):
    chain = HoloChain(tmp_path / "intervening_invalid.jsonl")
    original = chain.append({"claim": "Original"})
    operational = chain.append({
        "type": "service_append",
        "content": "Operational event",
    })
    real_append = chain.append

    def append_after_invalid_history(content, *args, **kwargs):
        real_append({
            "_holo_record_type": "holo_correction",
            "version": 1,
            "corrects_idx": operational["idx"],
            "corrects_hash": operational["hash"],
            "reason": "Intervening invalid correction",
            "replacement": {"claim": "Invalid"},
        })
        return real_append(content, *args, **kwargs)

    monkeypatch.setattr(chain, "append", append_after_invalid_history)

    with pytest.raises(ValueError):
        chain.correct(
            original["idx"],
            {"claim": "Replacement"},
            "Correction after intervening invalid history",
        )

    entries = chain.load_and_verify()
    assert len(entries) == 3
    assert entries[-1]["idx"] == 3
