import pytest

from holosim.x_delta_ingestor import XDeltaIngestor, stable_hash


def test_rejects_tampered_archived_source(tmp_path):
    ingestor = XDeltaIngestor(tmp_path / "chain.jsonl")

    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence"}],
        thread_ref="source-integrity-check",
    )

    packet["archive_raw"][0]["content"] = "altered source evidence"

    assert packet["source_hash"] != stable_hash(packet["archive_raw"])

    with pytest.raises(ValueError):
        ingestor.commit_reviewed(
            packet,
            reviewer="test-reviewer",
            approved=True,
        )

    assert ingestor.chain.load_and_verify() == []
