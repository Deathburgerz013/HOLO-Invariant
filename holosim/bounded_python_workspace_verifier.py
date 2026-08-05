"""Bounded deterministic verification for Python workspaces.

The verifier may compile and test files inside one supplied workspace.
It does not modify source files, install dependencies, grant acceptance,
or execute an inferred application entrypoint.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from holosim.canonical import stable_hash


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_OUTPUT_CHARS = 16_384

_IGNORED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
}


class BoundedPythonWorkspaceVerifierError(ValueError):
    """Raised when verifier configuration or workspace input is invalid."""


def _positive_number(value: Any, field: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value <= 0
    ):
        raise BoundedPythonWorkspaceVerifierError(
            f"{field} must be a positive number"
        )
    return float(value)


def _positive_int(value: Any, field: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
    ):
        raise BoundedPythonWorkspaceVerifierError(
            f"{field} must be a positive integer"
        )
    return value


def _bounded_text(value: str | None, limit: int) -> str:
    text = value or ""
    if len(text) <= limit:
        return text

    omitted = len(text) - limit
    return (
        text[:limit]
        + f"\n...[TRUNCATED {omitted} CHARACTERS]"
    )


def _run_command(
    command: Sequence[str],
    workspace: Path,
    *,
    timeout_seconds: float,
    max_output_chars: int,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": list(command),
            "returncode": None,
            "timed_out": True,
            "stdout": _bounded_text(
                exc.stdout
                if isinstance(exc.stdout, str)
                else "",
                max_output_chars,
            ),
            "stderr": _bounded_text(
                exc.stderr
                if isinstance(exc.stderr, str)
                else "",
                max_output_chars,
            ),
            "passed": False,
        }

    return {
        "command": list(command),
        "returncode": completed.returncode,
        "timed_out": False,
        "stdout": _bounded_text(
            completed.stdout,
            max_output_chars,
        ),
        "stderr": _bounded_text(
            completed.stderr,
            max_output_chars,
        ),
        "passed": completed.returncode == 0,
    }


def _python_files(workspace: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in workspace.rglob("*.py")
            if path.is_file()
            and not path.is_symlink()
            and not any(
                part in _IGNORED_PARTS
                for part in path.relative_to(workspace).parts
            )
        ),
        key=lambda path: path.relative_to(workspace).as_posix(),
    )


def _has_tests(workspace: Path) -> bool:
    return any(
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        for path in _python_files(workspace)
    )


def _detect_run_command(workspace: Path) -> str | None:
    candidates = (
        ("__main__.py", f"{sys.executable} __main__.py"),
        ("main.py", f"{sys.executable} main.py"),
        ("app.py", f"{sys.executable} app.py"),
    )

    for relative_path, command in candidates:
        if (workspace / relative_path).is_file():
            return command

    return None


class BoundedPythonWorkspaceVerifier:
    """Compile and optionally test one bounded Python workspace."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
        run_tests: bool = True,
    ) -> None:
        self._timeout_seconds = _positive_number(
            timeout_seconds,
            "timeout_seconds",
        )
        self._max_output_chars = _positive_int(
            max_output_chars,
            "max_output_chars",
        )

        if not isinstance(run_tests, bool):
            raise TypeError("run_tests must be a boolean")

        self._run_tests = run_tests
        self.last_receipt: dict[str, Any] | None = None

    def __call__(self, workspace: str | Path) -> dict[str, Any]:
        workspace_path = Path(workspace).resolve()

        if not workspace_path.is_dir():
            raise BoundedPythonWorkspaceVerifierError(
                "workspace must be an existing directory"
            )

        python_files = _python_files(workspace_path)

        if not python_files:
            body = {
                "passed": False,
                "runnable": False,
                "command": None,
                "reason": "NO_PYTHON_FILES",
                "feedback": "No Python files exist in the workspace",
                "checks": [],
                "python_files": [],
                "verified": False,
                "accepted": False,
                "write_authority": "NONE",
                "execution_authority": "BOUNDED_VERIFICATION_ONLY",
            }
            receipt = {
                **body,
                "receipt_hash": stable_hash(body),
            }
            self.last_receipt = deepcopy(receipt)
            return receipt

        checks: list[dict[str, Any]] = []

        compile_result = _run_command(
            (
                sys.executable,
                "-m",
                "compileall",
                "-q",
                ".",
            ),
            workspace_path,
            timeout_seconds=self._timeout_seconds,
            max_output_chars=self._max_output_chars,
        )
        compile_result["name"] = "compileall"
        checks.append(compile_result)

        if not compile_result["passed"]:
            reason = (
                "COMPILE_TIMEOUT"
                if compile_result["timed_out"]
                else "COMPILE_FAILED"
            )
            feedback = (
                compile_result["stderr"]
                or compile_result["stdout"]
                or reason
            )
            passed = False
        else:
            passed = True
            reason = "PYTHON_COMPILE_PASSED"
            feedback = None

        if (
            passed
            and self._run_tests
            and _has_tests(workspace_path)
        ):
            test_result = _run_command(
                (
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                ),
                workspace_path,
                timeout_seconds=self._timeout_seconds,
                max_output_chars=self._max_output_chars,
            )
            test_result["name"] = "pytest"
            checks.append(test_result)

            if not test_result["passed"]:
                passed = False
                reason = (
                    "TEST_TIMEOUT"
                    if test_result["timed_out"]
                    else "TESTS_FAILED"
                )
                feedback = (
                    test_result["stdout"]
                    or test_result["stderr"]
                    or reason
                )
            else:
                reason = "PYTHON_VERIFICATION_PASSED"
                feedback = None

        run_command = (
            _detect_run_command(workspace_path)
            if passed
            else None
        )
        runnable = passed and run_command is not None

        if passed and not runnable:
            reason = "ENTRYPOINT_COMMAND_MISSING"

        body = {
            "passed": passed,
            "runnable": runnable,
            "command": run_command,
            "reason": reason,
            "feedback": feedback,
            "checks": checks,
            "python_files": [
                path.relative_to(workspace_path).as_posix()
                for path in python_files
            ],
            "verified": passed,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "BOUNDED_VERIFICATION_ONLY",
        }

        receipt = {
            **body,
            "receipt_hash": stable_hash(body),
        }
        self.last_receipt = deepcopy(receipt)
        return receipt


def build_bounded_python_workspace_verifier(
    **kwargs: Any,
) -> BoundedPythonWorkspaceVerifier:
    """Build one verifier callable for capability or project checks."""

    return BoundedPythonWorkspaceVerifier(**kwargs)