from holosim.continuity_checkpoint import (
    build_continuity_checkpoint,
    verify_continuity_checkpoint,
)
from holosim.core import HoloChain


def test_checkpoint_preserves_ordered_effective_claims(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")

    first = chain.append({"claim": "The sky is green."})
    chain.append({"claim": "Continuity requires ordered evidence."})

    correction = chain.correct(
        first["idx"],
        {"claim": "The sky is blue."},
        reason="Corrected against observation.",
    )

    revalidation = chain.revalidate(
        first["idx"],
        outcome="HELD",
        evidence="Direct observation under daylight.",
        method="Visual comparison.",
    )

    checkpoint = build_continuity_checkpoint(chain)

    assert checkpoint["version"] == 1
    assert checkpoint["source"]["root_hash"] == revalidation["hash"]
    assert checkpoint["source"]["total_entries"] == 4

    assert [claim["idx"] for claim in checkpoint["claims"]] == [1, 2]

    first_claim = checkpoint["claims"][0]
    assert first_claim["content"] == {"claim": "The sky is blue."}
    assert first_claim["corrected_by"] == correction["idx"]
    assert first_claim["revalidated_by"] == revalidation["idx"]
    assert first_claim["status"] == "HELD"
    assert first_claim["correction_history"] == [correction["idx"]]
    assert first_claim["revalidation_history"] == [revalidation["idx"]]

    second_claim = checkpoint["claims"][1]
    assert second_claim["content"] == {
        "claim": "Continuity requires ordered evidence."
    }
    assert second_claim["status"] == "UNCHECKED"
    assert second_claim["correction_history"] == []
    assert second_claim["revalidation_history"] == []

    assert isinstance(checkpoint["checkpoint_hash"], str)
    assert len(checkpoint["checkpoint_hash"]) == 64


def test_checkpoint_is_deterministic_for_unchanged_chain(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")

    first = chain.append({"claim": "Original claim."})

    chain.correct(
        first["idx"],
        {"claim": "Corrected claim."},
        reason="Evidence changed the claim.",
    )

    chain.revalidate(
        first["idx"],
        outcome="HELD",
        evidence="Verified source record.",
        method="Source comparison.",
    )

    first_checkpoint = build_continuity_checkpoint(chain)
    second_checkpoint = build_continuity_checkpoint(chain)

    assert first_checkpoint == second_checkpoint
    assert (
        first_checkpoint["checkpoint_hash"]
        == second_checkpoint["checkpoint_hash"]
    )


def test_checkpoint_changes_when_chain_head_changes(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")

    chain.append({"claim": "First claim."})
    first_checkpoint = build_continuity_checkpoint(chain)

    chain.append({"claim": "Second claim."})
    second_checkpoint = build_continuity_checkpoint(chain)

    assert (
        first_checkpoint["source"]["root_hash"]
        != second_checkpoint["source"]["root_hash"]
    )
    assert (
        first_checkpoint["checkpoint_hash"]
        != second_checkpoint["checkpoint_hash"]
    )
    assert first_checkpoint["source"]["total_entries"] == 1
    assert second_checkpoint["source"]["total_entries"] == 2


def test_verify_accepts_valid_checkpoint(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")

    chain.append({"claim": "Continuity matters."})

    checkpoint = build_continuity_checkpoint(chain)
    result = verify_continuity_checkpoint(checkpoint)

    assert result["valid"] is True
    assert result["claim_count"] == 1
    assert result["checkpoint_hash"] == checkpoint["checkpoint_hash"]


def test_verify_rejects_tampered_checkpoint(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")

    chain.append({"claim": "Original"})
    checkpoint = build_continuity_checkpoint(chain)

    checkpoint["claims"][0]["content"] = {"claim": "Tampered"}

    import pytest

    with pytest.raises(ValueError, match="Claim content hash mismatch"):
        verify_continuity_checkpoint(checkpoint)
