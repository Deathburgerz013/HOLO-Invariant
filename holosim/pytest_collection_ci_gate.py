"""Read-only pytest collection loss gate across Git revisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from holosim.pytest_collection_continuity import (
    MAX_NODE_ID_LENGTH,
    compare_pytest_collections,
    observe_pytest_collection,
)

MARKER = "HOLO_COLLECTION_RESULT="

COLLECTOR = r"""
import json
import pytest

class Observer:
    def __init__(self):
        self.finished = False
        self.node_ids = []

    def pytest_collection_finish(self, session):
        self.finished = True
        self.node_ids = [item.nodeid for item in session.items]

observer = Observer()

code = pytest.main(
    [
        "tests",
        "--collect-only",
        "-q",
        "--ignore=Holo",
        "-p",
        "no:cacheprovider",
    ],
    plugins=[observer],
)

print("HOLO_COLLECTION_RESULT=" + json.dumps({
    "exit_code": int(code),
    "finished": observer.finished,
    "node_ids": observer.node_ids,
}))
"""


class CollectionGateError(RuntimeError):
    """Collection or revision comparison could not be trusted."""


def bounded_identity(value: str) -> str:
    """Encode a pytest node ID without relaxing the comparator's bounds."""
    if (
        type(value) is not str
        or not value
        or not value.strip()
        or "\x00" in value
    ):
        raise CollectionGateError("invalid pytest node ID")

    literal = "literal:" + value

    if len(literal) <= MAX_NODE_ID_LENGTH:
        return literal

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return "sha256:" + digest


def collect_revision(directory: Path, *, python_executable: Path | None = None) -> dict:
    """Collect identities in a separate Python process."""
    process = subprocess.run(
        [str(python_executable or sys.executable), "-c", COLLECTOR],
        cwd=directory,
        env=clean_collection_environment(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    records = [
        line[len(MARKER):]
        for line in process.stdout.splitlines()
        if line.startswith(MARKER)
    ]

    if process.returncode != 0 or len(records) != 1:
        raise CollectionGateError(
            "pytest collection process failed or returned invalid evidence"
            + "\n"
            + process.stdout[-1500:]
            + process.stderr[-1500:]
        )

    try:
        record = json.loads(records[0])
    except (ValueError, TypeError) as exc:
        raise CollectionGateError("invalid collection JSON") from exc

    if (
        type(record) is not dict
        or set(record) != {"exit_code", "finished", "node_ids"}
        or type(record["exit_code"]) is not int
        or record["exit_code"] != 0
        or record["finished"] is not True
        or type(record["node_ids"]) is not list
    ):
        raise CollectionGateError("incomplete pytest collection")

    original = record["node_ids"]

    if len(original) != len(set(original)):
        raise CollectionGateError("duplicate original pytest identity")

    bounded = [bounded_identity(value) for value in original]

    if len(bounded) != len(set(bounded)):
        raise CollectionGateError("bounded identity collision")

    return observe_pytest_collection(node_ids=bounded)


def git(*args: str, cwd: Path) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode:
        raise CollectionGateError(
            "git operation failed: "
            + " ".join(args)
            + "\n"
            + process.stderr[-1500:]
        )

    return process.stdout.strip()


def clean_collection_environment() -> dict[str, str]:
    """Prevent caller-controlled Python paths from crossing revision boundaries."""
    return {key: value for key, value in os.environ.items()
            if key.upper() not in {"PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}


def isolated_python(revision: Path, environment: Path) -> Path:
    """Install a revision in its own non-inheriting virtual environment."""
    if not (revision / "pyproject.toml").is_file():
        raise CollectionGateError("revision has no pyproject.toml")

    try:
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CollectionGateError("could not create isolated collection environment") from exc

    executable = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    try:
        process = subprocess.run(
            [str(executable), "-m", "pip", "install", "--disable-pip-version-check", "-e", ".[dev]"],
            cwd=revision,
            env=clean_collection_environment(),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectionGateError("isolated collection installation failed") from exc

    if process.returncode != 0:
        raise CollectionGateError(
            "isolated collection installation failed\n"
            + process.stdout[-1500:] + process.stderr[-1500:]
        )
    return executable


def compare_revisions(repository: Path, base_sha: str) -> dict:
    """Compare a supplied base commit with the checked-out candidate."""
    repository = repository.resolve()

    if not base_sha or not base_sha.strip():
        raise CollectionGateError("missing base SHA")

    base_commit = git(
        "rev-parse", "--verify", f"{base_sha}^{{commit}}",
        cwd=repository,
    )

    head_commit = git("rev-parse", "HEAD", cwd=repository)

    # Reject unrelated baselines.
    git(
        "merge-base", "--is-ancestor", base_commit, head_commit,
        cwd=repository,
    )

    with tempfile.TemporaryDirectory(prefix="holo-pytest-base-") as temp:
        base_directory = Path(temp) / "base"

        git(
            "worktree", "add", "--detach",
            str(base_directory), base_commit,
            cwd=repository,
        )

        try:
            # Separate environments prevent candidate-installed packages from
            # supplying imports to the historical pytest collection.
            base_python = isolated_python(base_directory, Path(temp) / "base-venv")
            head_python = isolated_python(repository, Path(temp) / "head-venv")
            previous = collect_revision(base_directory, python_executable=base_python)
            current = collect_revision(repository, python_executable=head_python)

            return compare_pytest_collections(
                previous=previous,
                current=current,
            )
        finally:
            git(
                "worktree", "remove", "--force",
                str(base_directory),
                cwd=repository,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--repository", default=".")
    args = parser.parse_args(argv)

    try:
        result = compare_revisions(
            Path(args.repository),
            args.base_sha,
        )
    except (
        CollectionGateError,
        subprocess.TimeoutExpired,
        ValueError,
    ) as exc:
        print(f"COLLECTION_GATE_ERROR: {exc}", file=sys.stderr)
        return 2

    print("STATUS:", result["status"])
    print("PREVIOUS_COUNT:", result["previous_count"])
    print("CURRENT_COUNT:", result["current_count"])
    print("MISSING_COUNT:", len(result["missing"]))
    print("ADDED_COUNT:", len(result["added"]))
    print("ACCEPTED:", result["accepted"])
    print("WRITE_AUTHORITY:", result["write_authority"])

    for missing in result["missing"][:20]:
        print("MISSING:", missing)

    if result["missing"]:
        print("COLLECTION_GATE_FAILED")
        return 1

    print("COLLECTION_GATE_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
