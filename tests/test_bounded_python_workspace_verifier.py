from __future__ import annotations

import sys

import pytest

from holosim.bounded_python_workspace_verifier import (
    BoundedPythonWorkspaceVerifierError,
    build_bounded_python_workspace_verifier,
)


def test_no_python_files_returns_deterministic_failure(tmp_path):
    verifier = build_bounded_python_workspace_verifier()

    result = verifier(tmp_path)

    assert result["passed"] is False
    assert result["runnable"] is False
    assert result["command"] is None
    assert result["reason"] == "NO_PYTHON_FILES"
    assert result["checks"] == []
    assert result["python_files"] == []
    assert result["verified"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_compile_only_workspace_passes_without_runnable_entrypoint(tmp_path):
    (tmp_path / "module.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["passed"] is True
    assert result["runnable"] is False
    assert result["command"] is None
    assert result["reason"] == "ENTRYPOINT_COMMAND_MISSING"
    assert result["checks"][0]["name"] == "compileall"
    assert result["checks"][0]["passed"] is True
    assert result["verified"] is True


def test_main_entrypoint_is_reported_as_runnable(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('ready')\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["passed"] is True
    assert result["runnable"] is True
    assert result["command"] == f"{sys.executable} main.py"
    assert result["reason"] == "PYTHON_COMPILE_PASSED"


def test_pytest_runs_when_test_files_exist(tmp_path):
    (tmp_path / "module.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "test_module.py").write_text(
        "from module import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["passed"] is True
    assert [check["name"] for check in result["checks"]] == [
        "compileall",
        "pytest",
    ]
    assert result["checks"][1]["passed"] is True
    assert result["reason"] == "ENTRYPOINT_COMMAND_MISSING"
    assert result["runtime_integrity"]["status"] == "PASS"
    assert [item["phase"] for item in result["runtime_integrity"]["observations"]] == [
        "after_compileall",
        "after_pytest",
    ]


def test_successful_test_that_mutates_source_aborts_with_receipt(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "test_mutation.py").write_text(
        "from pathlib import Path\n\n"
        "def test_mutate_source():\n"
        "    Path(__file__).with_name('module.py').write_text(" 
        "'VALUE = 2\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["checks"][-1]["name"] == "pytest"
    assert result["checks"][-1]["passed"] is True
    assert result["passed"] is False
    assert result["verified"] is False
    assert result["runnable"] is False
    assert result["reason"] == "RUNTIME_ARTIFACT_MISMATCH"
    assert result["runtime_integrity"]["status"] == "ABORT"
    assert result["runtime_integrity"]["observations"][-1]["differences"] == [
        "changed:module.py"
    ]
    assert result["runtime_integrity"]["mutation_applied"] is False
    assert result["runtime_integrity"]["automatic_repair"] is False


def test_runtime_integrity_baseline_binds_interpreter_and_sources(tmp_path):
    (tmp_path / "main.py").write_text("print('ready')\n", encoding="utf-8")

    result = build_bounded_python_workspace_verifier()(tmp_path)

    baseline = result["runtime_integrity"]["baseline"]
    assert baseline["sources"]["main.py"]["sha256"]
    assert baseline["executable"]["path"]
    assert baseline["executable"]["sha256"]
    assert baseline["snapshot_hash"]


def test_failed_tests_return_feedback(tmp_path):
    (tmp_path / "module.py").write_text(
        "def add(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
    )
    (tmp_path / "test_module.py").write_text(
        "from module import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["passed"] is False
    assert result["runnable"] is False
    assert result["reason"] == "TESTS_FAILED"
    assert "failed" in result["feedback"].lower()


def test_compile_failure_returns_feedback(tmp_path):
    (tmp_path / "broken.py").write_text(
        "def broken(:\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["passed"] is False
    assert result["reason"] == "COMPILE_FAILED"
    assert result["feedback"]


def test_run_tests_can_be_disabled(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('ready')\n",
        encoding="utf-8",
    )
    (tmp_path / "test_main.py").write_text(
        "def test_failure():\n"
        "    assert False\n",
        encoding="utf-8",
    )

    result = build_bounded_python_workspace_verifier(
        run_tests=False,
    )(tmp_path)

    assert result["passed"] is True
    assert result["runnable"] is True
    assert [check["name"] for check in result["checks"]] == [
        "compileall",
    ]


def test_symlinked_python_files_are_ignored(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    link = tmp_path / "link.py"

    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")

    result = build_bounded_python_workspace_verifier()(tmp_path)

    assert result["python_files"] == ["target.py"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"timeout_seconds": 0},
            "timeout_seconds must be a positive number",
        ),
        (
            {"max_output_chars": 0},
            "max_output_chars must be a positive integer",
        ),
    ],
)
def test_invalid_bounds_are_rejected(kwargs, message):
    with pytest.raises(
        BoundedPythonWorkspaceVerifierError,
        match=message,
    ):
        build_bounded_python_workspace_verifier(**kwargs)


def test_run_tests_must_be_boolean():
    with pytest.raises(
        TypeError,
        match="run_tests must be a boolean",
    ):
        build_bounded_python_workspace_verifier(
            run_tests="yes",
        )


def test_workspace_must_exist(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(
        BoundedPythonWorkspaceVerifierError,
        match="workspace must be an existing directory",
    ):
        build_bounded_python_workspace_verifier()(missing)


def test_last_receipt_is_copied(tmp_path):
    (tmp_path / "main.py").write_text(
        "print('ready')\n",
        encoding="utf-8",
    )
    verifier = build_bounded_python_workspace_verifier()

    result = verifier(tmp_path)

    assert verifier.last_receipt == result
    assert verifier.last_receipt is not result
