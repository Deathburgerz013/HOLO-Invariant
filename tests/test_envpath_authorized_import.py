"""Authorization and source-freshness boundaries for EnvPath imports."""

from holosim.core import HoloChain
from holosim.envpath import EnvPathWorkspace
from holosim.typed_operational_authorization import (
    ACTION_ENVPATH_NOTE_IMPORT,
    build_operational_authorization,
)


def test_stale_source_blocks_authorized_note_import(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    chain = HoloChain(path)
    chain.append({"observation": "initial"})

    workspace = EnvPathWorkspace(path)
    draft = workspace.draft("note", "Proposed additional observation.")

    authorization = build_operational_authorization(
        authorization_id="envpath-import-1",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:envpath-import-1",
    )

    chain.append({"observation": "source changed after proposal"})

    before = path.read_bytes()

    result = import_note_draft(
        path,
        draft=draft,
        authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert path.read_bytes() == before



def test_authorized_note_import_commits_once(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    chain = HoloChain(path)
    chain.append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft(
        "note", "Proposed additional observation."
    )
    authorization = build_operational_authorization(
        authorization_id="envpath-import-once",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:envpath-import-once",
    )

    first = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert first["status"] == "COMMITTED"
    assert first["commit_performed"] is True
    assert first["accepted"] is False
    assert first["truth_claimed"] is False

    entries = HoloChain(path).load_and_verify()
    assert len(entries) == 2

    replay = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert replay["status"] == "BLOCKED"
    assert replay["commit_performed"] is False
    assert HoloChain(path).load_and_verify() == entries



def test_reused_authorization_id_blocks_fresh_proposal(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    first_draft = EnvPathWorkspace(path).draft("note", "First note")
    first_auth = build_operational_authorization(
        authorization_id="shared-import-id",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=first_draft["draft_hash"],
        approval_reference="review:first",
    )

    first = import_note_draft(
        path, draft=first_draft, authorization=first_auth,
    )
    assert first["status"] == "COMMITTED"

    second_draft = EnvPathWorkspace(path).draft("note", "Second note")
    second_auth = build_operational_authorization(
        authorization_id="shared-import-id",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=second_draft["draft_hash"],
        approval_reference="review:second",
    )

    before = path.read_bytes()
    second = import_note_draft(
        path, draft=second_draft, authorization=second_auth,
    )

    assert second["status"] == "BLOCKED"
    assert second["commit_performed"] is False
    assert "consumed" in second["reason"]
    assert path.read_bytes() == before



def test_tampered_note_draft_is_rejected(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft("note", "Original note")
    authorization = build_operational_authorization(
        authorization_id="tamper-test-1",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:tamper-test-1",
    )

    tampered = dict(draft)
    tampered["content"] = "Unauthorized replacement"

    before = path.read_bytes()

    result = import_note_draft(
        path,
        draft=tampered,
        authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert "draft hash mismatch" in result["reason"]
    assert path.read_bytes() == before



def test_post_commit_verification_failure_preserves_commit_status(
    tmp_path, monkeypatch,
):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft("note", "Verification failure test")
    authorization = build_operational_authorization(
        authorization_id="post-commit-failure",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:post-commit-failure",
    )

    original_verify = HoloChain.load_and_verify
    calls = 0

    def fail_post_commit_verification(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise OSError("simulated post-commit verification failure")
        return original_verify(self, *args, **kwargs)

    monkeypatch.setattr(
        HoloChain, "load_and_verify", fail_post_commit_verification,
    )

    result = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert result["status"] == "COMMITTED_UNVERIFIED"
    assert result["commit_performed"] is True
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert path.exists()



def test_append_fsync_failure_reports_unknown_outcome(tmp_path, monkeypatch):
    import os

    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft("note", "Uncertain persistence")
    authorization = build_operational_authorization(
        authorization_id="fsync-failure",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:fsync-failure",
    )

    original_fsync = os.fsync

    def fail_fsync(fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    try:
        result = import_note_draft(
            path, draft=draft, authorization=authorization,
        )
    finally:
        monkeypatch.setattr(os, "fsync", original_fsync)

    assert result["status"] == "OUTCOME_UNKNOWN"
    assert result["commit_performed"] is None
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert "fsync" in result["reason"]



def test_post_commit_payload_mismatch_is_not_verified(tmp_path, monkeypatch):
    import json

    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft("note", "Authorized note")
    authorization = build_operational_authorization(
        authorization_id="payload-mismatch",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:payload-mismatch",
    )

    original_verify = HoloChain.load_and_verify
    calls = 0

    def substitute_post_commit_payload(self, *args, **kwargs):
        nonlocal calls
        entries = original_verify(self, *args, **kwargs)
        calls += 1

        if calls >= 2 and len(entries) >= 2:
            entries = [dict(entry) for entry in entries]
            payload = json.loads(entries[-1]["content"])
            payload["content"] = "Different reconstructed note"
            entries[-1]["content"] = json.dumps(payload)

        return entries

    monkeypatch.setattr(
        HoloChain, "load_and_verify", substitute_post_commit_payload,
    )

    result = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert result["status"] == "COMMITTED_UNVERIFIED"
    assert result["commit_performed"] is True
    assert result["accepted"] is False
    assert result["truth_claimed"] is False



def test_concurrent_imports_from_same_snapshot_commit_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft(
        "note", "Concurrent proposal"
    )

    authorizations = [
        build_operational_authorization(
            authorization_id=f"concurrent-import-{i}",
            actor_id="external-reviewer",
            action=ACTION_ENVPATH_NOTE_IMPORT,
            target_sha256=draft["draft_hash"],
            approval_reference=f"review:concurrent-{i}",
        )
        for i in range(2)
    ]

    barrier = Barrier(2)

    def attempt(authorization):
        barrier.wait(timeout=10)
        return import_note_draft(
            path,
            draft=draft,
            authorization=authorization,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, authorization)
            for authorization in authorizations
        ]
        results = [future.result(timeout=15) for future in futures]

    assert sorted(result["status"] for result in results) == [
        "BLOCKED",
        "COMMITTED",
    ]

    assert sum(
        result["commit_performed"] is True
        for result in results
    ) == 1

    entries = HoloChain(path).load_and_verify()
    assert len(entries) == 2



def test_wrong_authorization_action_blocks_import(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft
    from holosim.typed_operational_authorization import ACTION_SERVICE_APPEND

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft(
        "note", "Wrong-action proposal"
    )

    authorization = build_operational_authorization(
        authorization_id="wrong-action-import",
        actor_id="external-reviewer",
        action=ACTION_SERVICE_APPEND,
        target_sha256=draft["draft_hash"],
        approval_reference="review:wrong-action-import",
    )

    before = path.read_bytes()

    result = import_note_draft(
        path,
        draft=draft,
        authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert "action does not match" in result["reason"]
    assert path.read_bytes() == before



def test_import_survives_fresh_process_reconstruction(tmp_path):
    import json
    import subprocess
    import sys

    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    HoloChain(path).append({"observation": "initial"})

    draft = EnvPathWorkspace(path).draft(
        "note", "Persistent reconstruction evidence"
    )

    authorization = build_operational_authorization(
        authorization_id="fresh-process-import",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:fresh-process-import",
    )

    result = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert result["status"] == "COMMITTED"

    script = """
import json
import sys
from holosim.core import HoloChain

entries = HoloChain(sys.argv[1]).load_and_verify()
payload = json.loads(entries[-1]["content"])

print(json.dumps({
    "entry_count": len(entries),
    "entry_hash": entries[-1]["hash"],
    "payload": payload,
}))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )

    reconstructed = json.loads(completed.stdout)

    assert reconstructed["entry_count"] == 2
    assert reconstructed["entry_hash"] == result["entry"]["hash"]

    payload = reconstructed["payload"]

    assert payload["type"] == "envpath_imported_note"
    assert payload["content"] == draft["content"]
    assert payload["draft_hash"] == draft["draft_hash"]
    assert payload["source_sha256"] == draft["source_sha256"]
    assert payload["operational_authorization"] == authorization
    assert payload["accepted"] is False
    assert payload["truth_claimed"] is False



def test_unrelated_authorization_field_does_not_consume_import(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"

    HoloChain(path).append({
        "type": "unrelated_observation",
        "operational_authorization": {
            "authorization_id": "shared-unrelated-id",
        },
    })

    draft = EnvPathWorkspace(path).draft("note", "Independent note")
    authorization = build_operational_authorization(
        authorization_id="shared-unrelated-id",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:unrelated",
    )

    result = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert result["status"] == "COMMITTED"
    assert len(HoloChain(path).load_and_verify()) == 2


def test_malformed_imported_authorization_blocks_import(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"

    HoloChain(path).append({
        "type": "envpath_imported_note",
        "version": 1,
        "operational_authorization": {
            "authorization_id": "malformed-prior",
        },
    })

    draft = EnvPathWorkspace(path).draft("note", "New proposal")
    authorization = build_operational_authorization(
        authorization_id="new-valid-import",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:new-valid-import",
    )

    before = path.read_bytes()

    result = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert path.read_bytes() == before



def test_incomplete_prior_import_payload_blocks_import(tmp_path):
    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"

    prior_authorization = build_operational_authorization(
        authorization_id="prior-incomplete-import",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256="a" * 64,
        approval_reference="review:prior-incomplete",
    )

    HoloChain(path).append({
        "type": "envpath_imported_note",
        "version": 1,
        "operational_authorization": prior_authorization,
    })

    draft = EnvPathWorkspace(path).draft("note", "New proposal")
    authorization = build_operational_authorization(
        authorization_id="new-import-after-incomplete",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:new-import",
    )

    before = path.read_bytes()

    result = import_note_draft(
        path, draft=draft, authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert path.read_bytes() == before

def test_compressed_history_decode_failure_blocks_without_writing(tmp_path, monkeypatch):
    import zlib

    from holosim.envpath_authorized_import import import_note_draft

    path = tmp_path / "memory.jsonl"
    chain = HoloChain(path)
    chain.append(
        {"observation": "repeated-evidence-" * 100},
        compress=True,
    )

    entries = chain.load_and_verify()
    assert len(entries) == 1
    assert entries[0]["type"] == "compressed"

    draft = EnvPathWorkspace(path).draft(
        "note", "Compressed history regression"
    )
    authorization = build_operational_authorization(
        authorization_id="compressed-history-regression",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:compressed-history-regression",
    )

    before = path.read_bytes()

    def fail_decompression(*args, **kwargs):
        raise zlib.error("simulated decompression failure")

    monkeypatch.setattr(zlib, "decompressobj", fail_decompression)

    result = import_note_draft(
        path,
        draft=draft,
        authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert path.read_bytes() == before

def test_oversized_compressed_history_blocks_without_writing(tmp_path):
    import hashlib

    from holosim.envpath_authorized_import import import_note_draft
    from holosim.replay import MAX_SEARCH_DECODED_BYTES

    path = tmp_path / "memory.jsonl"
    chain = HoloChain(path)

    chain.append(
        {"observation": "A" * (MAX_SEARCH_DECODED_BYTES + 1)},
        compress=True,
    )

    entries = chain.load_and_verify()
    assert len(entries) == 1
    assert entries[0]["type"] == "compressed"

    before = path.read_bytes()

    supplied_snapshot = {
        "head_hash": entries[-1]["hash"],
        "source_sha256": hashlib.sha256(before).hexdigest(),
    }

    draft = EnvPathWorkspace(path).draft(
        "note",
        "Oversized compressed history regression",
        snapshot=supplied_snapshot,
    )

    authorization = build_operational_authorization(
        authorization_id="oversized-compressed-history",
        actor_id="external-reviewer",
        action=ACTION_ENVPATH_NOTE_IMPORT,
        target_sha256=draft["draft_hash"],
        approval_reference="review:oversized-compressed-history",
    )

    result = import_note_draft(
        path,
        draft=draft,
        authorization=authorization,
    )

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert path.read_bytes() == before
