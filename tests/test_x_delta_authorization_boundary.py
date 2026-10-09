from holosim.x_delta_ingestor import XDeltaIngestor
from holosim.typed_operational_authorization import (
    ACTION_X_DELTA_INGEST,
    build_operational_authorization,
    validate_operational_authorization,
)



def test_approval_flag_alone_cannot_authorize_x_delta_append(tmp_path):
    ingestor = XDeltaIngestor(tmp_path / "chain.jsonl")
    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence"}],
        thread_ref="authorization-boundary",
    )

    result = ingestor.commit_reviewed(
        packet,
        reviewer="claimed-reviewer",
        approved=True,
    )

    assert result["appended"] is False
    assert ingestor.chain.load_and_verify() == []


def test_x_delta_authorization_has_its_own_target_bound_action():
    authorization = build_operational_authorization(
        authorization_id="approval:x-delta-1",
        actor_id="external-reviewer",
        action="X_DELTA_INGEST",
        target_sha256="a" * 64,
        approval_reference="approval:x-delta-1",
    )

    assert validate_operational_authorization(
        authorization,
        expected_action="X_DELTA_INGEST",
        expected_target_sha256="a" * 64,
    )
    assert authorization["write_authority"] == "EXACT_TARGET_ONLY"
    assert authorization["truth_claimed"] is False


def test_authorized_x_delta_commit_is_single_use(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    ingestor = XDeltaIngestor(chain_path)
    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence"}],
        thread_ref="authorized-thread",
    )

    authorization = build_operational_authorization(
        authorization_id="approval:x-delta-commit-1",
        actor_id="external-reviewer",
        action=ACTION_X_DELTA_INGEST,
        target_sha256=packet["review_hash"],
        approval_reference="approval:x-delta-commit-1",
    )

    first = ingestor.commit_reviewed(
        packet,
        reviewer="external-reviewer",
        approved=True,
        authorization=authorization,
    )

    assert first["status"] == "committed"
    assert first["appended"] is True
    assert len(ingestor.chain.load_and_verify()) == 1

    second = XDeltaIngestor(chain_path).commit_reviewed(
        packet,
        reviewer="external-reviewer",
        approved=True,
        authorization=authorization,
    )

    assert second["appended"] is False
    assert len(ingestor.chain.load_and_verify()) == 1


def test_compressed_chain_entry_cannot_reuse_authorization(tmp_path):
    import json

    ingestor = XDeltaIngestor(tmp_path / "chain.jsonl")
    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence " * 2000}],
        thread_ref="compressed-replay",
    )
    authorization = build_operational_authorization(
        authorization_id="approval:compressed-replay-1",
        actor_id="external-reviewer",
        action=ACTION_X_DELTA_INGEST,
        target_sha256=packet["review_hash"],
        approval_reference="approval:compressed-replay-1",
    )

    previous = ingestor.prepare_commit(
        packet,
        reviewer="external-reviewer",
    )
    previous["operational_authorization"] = dict(authorization)

    ingestor.chain.append(
        json.dumps(previous),
        compress=True,
        min_compress_size=1,
    )

    before = ingestor.chain.load_and_verify()
    assert len(before) == 1
    assert before[0]["type"] == "compressed"

    result = ingestor.commit_reviewed(
        packet,
        reviewer="external-reviewer",
        approved=True,
        authorization=authorization,
    )

    assert result["status"] == "blocked"
    assert result["appended"] is False
    assert len(ingestor.chain.load_and_verify()) == 1
