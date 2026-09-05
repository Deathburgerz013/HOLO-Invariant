from __future__ import annotations

import subprocess
from copy import deepcopy

import pytest

from holosim.genesis_origins import (
    GenesisOriginError,
    _canonical_hash,
    observe_repository_path_genesis,
    verify_genesis_origin_receipt,
)


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def repository(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Test Operator")
    git(tmp_path, "config", "user.email", "operator@example.invalid")
    return tmp_path


def commit_file(root, path, text, message):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    git(root, "add", path)
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_unique_exact_path_genesis_is_pinned_and_rebuildable(tmp_path) -> None:
    root = repository(tmp_path)
    origin = commit_file(root, "holosim/worker.py", "VALUE = 1\n", "add worker")
    head = commit_file(root, "holosim/worker.py", "VALUE = 2\n", "change worker")
    receipt = observe_repository_path_genesis(
        root=root, path="holosim/worker.py"
    )
    assert receipt["status"] == "UNIQUE"
    assert receipt["head_commit"] == head
    assert [item["commit"] for item in receipt["addition_events"]] == [origin]
    assert receipt["genesis_candidates"] == receipt["addition_events"]
    assert verify_genesis_origin_receipt(receipt, root=root)["status"] == "PASS"


def test_later_head_does_not_change_pinned_receipt(tmp_path) -> None:
    root = repository(tmp_path)
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    receipt = observe_repository_path_genesis(root=root, path="worker.py")
    commit_file(root, "other.py", "OTHER = 1\n", "later")
    assert verify_genesis_origin_receipt(receipt, root=root)["status"] == "PASS"


def test_delete_and_readd_is_recorded_but_not_a_second_genesis(tmp_path) -> None:
    root = repository(tmp_path)
    first = commit_file(root, "worker.py", "VALUE = 1\n", "add")
    (root / "worker.py").unlink()
    git(root, "add", "worker.py")
    git(root, "commit", "-q", "-m", "delete")
    second = commit_file(root, "worker.py", "VALUE = 2\n", "readd")
    receipt = observe_repository_path_genesis(root=root, path="worker.py")
    assert {item["commit"] for item in receipt["addition_events"]} == {first, second}
    assert [item["commit"] for item in receipt["genesis_candidates"]] == [first]


def test_rename_is_not_silently_treated_as_exact_path_origin(tmp_path) -> None:
    root = repository(tmp_path)
    commit_file(root, "old.py", "VALUE = 1\n", "old")
    git(root, "mv", "old.py", "new.py")
    git(root, "commit", "-q", "-m", "rename")
    receipt = observe_repository_path_genesis(root=root, path="new.py")
    assert receipt["rename_followed"] is False
    assert receipt["genesis_candidates"][0]["commit"] == git(root, "rev-parse", "HEAD")
    assert "rename or copy lineage" in receipt["interpretation_notice"]


@pytest.mark.parametrize("path", ["", "../outside.py", "/absolute.py", r"x\\y.py"])
def test_unsafe_or_ambiguous_paths_fail_closed(tmp_path, path) -> None:
    root = repository(tmp_path)
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    with pytest.raises(GenesisOriginError):
        observe_repository_path_genesis(root=root, path=path)


def test_missing_path_and_non_repository_fail_closed(tmp_path) -> None:
    with pytest.raises(GenesisOriginError, match="Git observation failed"):
        observe_repository_path_genesis(root=tmp_path, path="missing.py")
    root = repository(tmp_path / "repo")
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    with pytest.raises(GenesisOriginError):
        observe_repository_path_genesis(root=root, path="missing.py")


def test_source_change_after_pinned_commit_does_not_rewrite_history(tmp_path) -> None:
    root = repository(tmp_path)
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    receipt = observe_repository_path_genesis(root=root, path="worker.py")
    (root / "worker.py").write_text("UNCOMMITTED = True\n", encoding="utf-8")
    assert verify_genesis_origin_receipt(receipt, root=root)["status"] == "PASS"


def test_tampered_origin_is_detected(tmp_path) -> None:
    root = repository(tmp_path)
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    receipt = observe_repository_path_genesis(root=root, path="worker.py")
    tampered = deepcopy(receipt)
    tampered["head_blob"] = "0" * 40
    result = verify_genesis_origin_receipt(tampered, root=root)
    assert result["status"] == "FAIL"
    assert result["failures"] == ["head_blob_mismatch", "receipt_hash_mismatch"]


def test_rehashed_authority_claim_still_fails(tmp_path) -> None:
    root = repository(tmp_path)
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    receipt = observe_repository_path_genesis(root=root, path="worker.py")
    receipt["accepted"] = True
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = _canonical_hash(body)
    result = verify_genesis_origin_receipt(receipt, root=root)
    assert result["status"] == "FAIL"
    assert result["failures"] == ["forbidden_authority"]


def test_receipt_refuses_absolute_authorship_and_authority(tmp_path) -> None:
    root = repository(tmp_path)
    commit_file(root, "worker.py", "VALUE = 1\n", "add")
    receipt = observe_repository_path_genesis(root=root, path="worker.py")
    assert "authorship" in receipt["interpretation_notice"]
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
