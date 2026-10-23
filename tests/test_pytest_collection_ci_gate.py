"""Regression tests for the cross-revision pytest collection gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from holosim.pytest_collection_ci_gate import (
    CollectionGateError,
    bounded_identity,
    collect_revision,
    compare_revisions,
)


def test_short_identity_is_literal():
    assert bounded_identity("tests/test_a.py::test_a") == (
        "literal:tests/test_a.py::test_a"
    )


def test_oversized_identity_is_bounded():
    value = "tests/test_a.py::test_large[" + "x" * 16000 + "]"
    result = bounded_identity(value)

    assert result.startswith("sha256:")
    assert len(result) == 71
    assert result == bounded_identity(value)


def test_different_oversized_identities_remain_distinct():
    first = bounded_identity("x" * 16000)
    second = bounded_identity("y" * 16000)

    assert first != second


def test_literal_namespace_cannot_impersonate_digest_namespace():
    digest_like = "sha256:" + "a" * 64
    assert bounded_identity(digest_like) == "literal:" + digest_like


@pytest.mark.parametrize("value", ["", " ", "a\x00b", None, 12])
def test_invalid_identity_rejected(value):
    with pytest.raises(CollectionGateError):
        bounded_identity(value)


def test_prefix_boundary_is_respected():
    assert len(bounded_identity("x" * 4088)) == 4096
    assert len(bounded_identity("x" * 4089)) == 71


def test_real_pytest_collection(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_example.py").write_text(
        "def test_alpha(): pass\n"
        "def test_beta(): pass\n",
        encoding="utf-8",
    )

    observation = collect_revision(tmp_path)

    assert observation["count"] == 2
    assert observation["accepted"] is False
    assert observation["write_authority"] == "NONE"


def test_collection_failure_is_not_silent(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_broken.py").write_text(
        "def test_broken(:\n",
        encoding="utf-8",
    )

    with pytest.raises(CollectionGateError):
        collect_revision(tmp_path)


def _git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=directory,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_deleted_test_is_detected_across_commits(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.name", "HOLO Test")
    _git(repo, "config", "user.email", "holo@example.invalid")

    tests = repo / "tests"
    tests.mkdir()

    test_file = tests / "test_example.py"
    test_file.write_text(
        "def test_alpha(): pass\n"
        "def test_beta(): pass\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    base = _git(repo, "rev-parse", "HEAD")

    test_file.write_text(
        "def test_alpha(): pass\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "remove beta")

    result = compare_revisions(repo, base)

    assert result["status"] == "LOSS_DETECTED"
    assert result["previous_count"] == 2
    assert result["current_count"] == 1
    assert len(result["missing"]) == 1
    assert result["missing"][0].endswith("::test_beta")
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
