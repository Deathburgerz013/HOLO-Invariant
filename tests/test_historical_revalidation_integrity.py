from holosim.core import HoloChain


def test_later_correction_preserves_historical_receipt(tmp_path):
    chain = HoloChain(tmp_path / "history.jsonl")

    original = chain.append({"claim": "Original"})
    receipt = chain.revalidate(
        original["idx"],
        "HELD",
        "Original evidence",
        "Original method",
    )

    before = chain.get_revalidations(original["idx"])
    assert len(before) == 1
    assert before[0]["current"] is True

    correction = chain.correct(
        original["idx"],
        {"claim": "Corrected"},
        "New evidence",
    )

    after = chain.get_revalidations(original["idx"])

    assert len(after) == 1
    assert after[0]["idx"] == receipt["idx"]
    assert after[0]["outcome"] == "HELD"
    assert after[0]["subject_correction_idx"] is None
    assert after[0]["subject_hash"] == before[0]["subject_hash"]
    assert after[0]["current"] is False

    claims = chain.get_claim_index()
    claim = next(item for item in claims if item["idx"] == original["idx"])

    assert claim["content"] == {"claim": "Corrected"}
    assert claim["correction_history"] == [correction["idx"]]
    assert claim["revalidation_history"] == [receipt["idx"]]
    assert claim["status"] != "HELD"

    new_receipt = chain.revalidate(
        original["idx"],
        "HELD",
        "Updated evidence",
        "Updated method",
    )

    checks = chain.get_revalidations(original["idx"])

    assert [check["current"] for check in checks] == [False, True]
    assert checks[1]["idx"] == new_receipt["idx"]
    assert checks[1]["subject_correction_idx"] == correction["idx"]
