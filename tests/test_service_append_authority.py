import hashlib
import json

from holosim.collector import Collector
from holosim.service import HoloService
from holosim.typed_operational_authorization import (
    ACTION_SERVICE_APPEND,
    build_operational_authorization,
)


def _authorization(content, reference="review:service-1"):
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return build_operational_authorization(
        authorization_id=reference,
        actor_id="Canyon Haney",
        action=ACTION_SERVICE_APPEND,
        target_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        approval_reference=reference,
    )


def test_service_append_is_blocked_without_external_approval(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    slot_path = tmp_path / "slots.db"
    service = HoloService(chain_path, slot_db_path=slot_path)

    result = service.append(
        "candidate content",
        compress=False,
        mirror_to_slots=True,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert result["mutation"] is None
    assert result["entry"] is None
    assert result["slot"] is None
    assert result["authority"]["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert not chain_path.exists()
    assert not slot_path.exists()


def test_service_append_rejects_untyped_authority_fields(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    service = HoloService(chain_path)

    result = service.append(
        "candidate content",
    )

    assert result["status"] == "BLOCKED"
    assert result["authority"]["authorization_hash"] is None
    assert not chain_path.exists()


def test_service_append_records_external_authority_and_content_hash(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    service = HoloService(chain_path)
    content = {"claim": "camera records motion"}

    result = service.append(
        content,
        compress=False,
        authorization=_authorization(content),
    )

    assert result["status"] == "COMMITTED"
    assert result["commit_performed"] is True
    assert result["write_authority"] == "EXTERNAL_HUMAN"
    assert result["authority"] == {
        "accepted": True,
        "source": "external_human",
        "reviewer": "Canyon Haney",
        "approval_reference": "review:service-1",
    }
    assert result["operational_authorization"] == _authorization(content)

    entry = json.loads(chain_path.read_text(encoding="utf-8").splitlines()[0])
    payload = json.loads(entry["content"])
    canonical = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert payload["content_sha256"] == hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    assert payload["authority"] == result["authority"]
    assert payload["operational_authorization"] == _authorization(content)


def test_collector_does_not_report_blocked_append_as_collected(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    collector = Collector(chain_path)

    result = collector.collect_text(
        "candidate content",
        force=True,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "external_approval_required"
    assert result["append"]["commit_performed"] is False
    assert not chain_path.exists()


def test_collector_threads_external_authority_to_service(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    collector = Collector(chain_path)

    result = collector.collect_text(
        "candidate content",
        force=True,
        reviewer="Canyon Haney",
        approval_reference="review:collector-1",
    )

    assert result["status"] == "collected"
    assert result["append"]["status"] == "COMMITTED"
    assert result["append"]["authority"]["approval_reference"] == (
        "review:collector-1"
    )
    assert result["verify"]["status"] == "ok"
