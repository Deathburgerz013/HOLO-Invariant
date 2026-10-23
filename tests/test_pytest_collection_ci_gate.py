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

    # Disposable revisions must be installable for isolated collection.
    (repo / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools>=45"]\n'
        'build-backend = "setuptools.build_meta"\n'
        '[project]\nname = "holo-collection-fixture"\nversion = "0.0.1"\n'
        '[project.optional-dependencies]\ndev = ["pytest>=8"]\n',
        encoding="utf-8",
    )
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


def test_historical_collection_uses_historical_package(tmp_path, monkeypatch):
    """A candidate package rename must not break historical collection."""
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.name", "HOLO Test")
    _git(repo, "config", "user.email", "holo@example.invalid")

    (repo / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools>=45"]\n'
        'build-backend = "setuptools.build_meta"\n'
        '[project]\nname = "holo-import-boundary-fixture"\n'
        'version = "0.0.1"\n'
        '[tool.setuptools.packages.find]\nwhere = ["."]\n'
        '[project.optional-dependencies]\ndev = ["pytest>=8"]\n',
        encoding="utf-8",
    )

    package = repo / "boundary_fixture"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "old_module.py").write_text("VALUE = 42\n", encoding="utf-8")

    tests = repo / "tests"
    tests.mkdir()
    test_file = tests / "test_boundary.py"
    test_file.write_text(
        "from boundary_fixture.old_module import VALUE\n"
        "def test_identity():\n"
        "    assert VALUE == 42\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "historical module")
    base = _git(repo, "rev-parse", "HEAD")

    (package / "old_module.py").unlink()
    (package / "new_module.py").write_text("VALUE = 42\n", encoding="utf-8")
    test_file.write_text(
        "from boundary_fixture.new_module import VALUE\n"
        "def test_identity():\n"
        "    assert VALUE == 42\n",
        encoding="utf-8",
    )

    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "rename module without losing test")

    # Attempt to contaminate both collection processes.
    monkeypatch.setenv("PYTHONPATH", str(repo))

    result = compare_revisions(repo, base)

    assert result["status"] == "PRESERVED"
    assert result["missing"] == []
    assert result["previous_count"] == 1
    assert result["current_count"] == 1
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
