import pytest

from holosim.x_delta_ingestor import XDeltaIngestor
from holosim.typed_operational_authorization import (
    ACTION_X_DELTA_INGEST,
    build_operational_authorization,
)


def test_rejects_tampered_review_packet(tmp_path):
    ingestor = XDeltaIngestor(tmp_path / "chain.jsonl")

    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence"}],
        thread_ref="test-thread",
    )

    original_hash = packet["review_hash"]
    packet["critical"][0]["content"] = "modified after review"

    assert packet["review_hash"] == original_hash

    with pytest.raises(ValueError):
        ingestor.commit_reviewed(
            packet,
            reviewer="test-reviewer",
            approved=True,
        )

    assert ingestor.chain.load_and_verify() == []


def test_accepts_unchanged_approved_review_packet(tmp_path):
    ingestor = XDeltaIngestor(tmp_path / "chain.jsonl")

    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence"}],
        thread_ref="test-thread",
    )

    authorization = build_operational_authorization(
        authorization_id="approval:review-integrity-1",
        actor_id="test-reviewer",
        action=ACTION_X_DELTA_INGEST,
        target_sha256=packet["review_hash"],
        approval_reference="approval:review-integrity-1",
    )

    result = ingestor.commit_reviewed(
        packet,
        reviewer="test-reviewer",
        approved=True,
        authorization=authorization,
    )

    assert result["status"] == "committed"
    assert result["appended"] is True
    assert result["review_hash"] == packet["review_hash"]
    assert len(ingestor.chain.load_and_verify()) == 1
