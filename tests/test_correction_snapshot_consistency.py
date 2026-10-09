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
