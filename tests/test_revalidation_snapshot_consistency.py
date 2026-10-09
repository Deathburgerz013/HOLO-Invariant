from holosim.core import HoloChain


def test_revalidation_uses_one_verified_snapshot(tmp_path, monkeypatch):
    chain = HoloChain(tmp_path / "snapshot.jsonl")

    original = chain.append({"claim": "Original"})
    correction = chain.correct(
        original["idx"],
        {"claim": "Corrected"},
        "New evidence",
    )

    entries, decoded, corrections = chain._correction_view()
    expected = chain._effective_state_from_correction_view(
        entries, decoded, corrections
    )
    subject = next(
        item for item in expected if item["idx"] == original["idx"]
    )

    def inconsistent_second_read():
        raise AssertionError(
            "Revalidation independently reconstructed effective state"
        )

    monkeypatch.setattr(
        chain, "get_effective_state", inconsistent_second_read
    )

    receipt = chain.revalidate(
        original["idx"],
        "HELD",
        "Verified evidence",
        "Snapshot comparison",
    )

    stored = chain.get_state()[-1]

    assert receipt["idx"] == correction["idx"] + 1
    assert stored["target_hash"] == original["hash"]
    assert stored["subject_hash"] == chain._content_digest(
        subject["content"]
    )
    assert stored["subject_correction_idx"] == correction["idx"]
