import json

from holosim.typed_operational_authorization import (
    ACTION_X_DELTA_INGEST,
    build_operational_authorization,
)
from holosim.x_delta_ingestor import XDeltaIngestor


def test_compression_type_cannot_hide_consumed_authorization(tmp_path):
    path = tmp_path / "chain.jsonl"
    ingestor = XDeltaIngestor(path)

    packet = ingestor.extract_deltas(
        [{"id": "1", "text": "continuity evidence"}],
        thread_ref="malformed-compression-replay",
    )
    authorization = build_operational_authorization(
        authorization_id="approval:malformed-compression",
        actor_id="external-reviewer",
        action=ACTION_X_DELTA_INGEST,
        target_sha256=packet["review_hash"],
        approval_reference="approval:malformed-compression",
    )

    previous = ingestor.prepare_commit(
        packet, reviewer="external-reviewer"
    )
    previous["operational_authorization"] = dict(authorization)
    ingestor.chain.append(json.dumps(previous))

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    entry["type"] = "compressed"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    result = ingestor.commit_reviewed(
        packet,
        reviewer="external-reviewer",
        approved=True,
        authorization=authorization,
    )

    assert result["appended"] is False
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
