"""Bounded pytest evidence adapter for the generic Holo/Sim hook contract.

This adapter executes only explicit pytest node/path targets through the current
Python interpreter. It returns captured process observations as hook evidence;
it does not treat a passing test as truth, acceptance, or write authority.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from holosim.hook_contract import (
    HookContractError,
    build_hook_result,
    validate_hook_request,
)

PYTEST_HOOK_ID = "pytest"
PYTEST_ACTION = "run_targets"
MAX_TARGETS = 32
MAX_OUTPUT_CHARS = 100_000


def _validate_targets(value: Any) -> list[str]:
    if type(value) not in {list, tuple} or not value:
        raise HookContractError("pytest payload targets must be a nonempty list or tuple")
    if len(value) > MAX_TARGETS:
        raise HookContractError("pytest payload exceeds maximum target count")
    targets: list[str] = []
    for target in value:
        if type(target) is not str or not target.strip():
            raise HookContractError("pytest targets must be nonempty plain strings")
        if target.startswith("-"):
            raise HookContractError("pytest targets must not be command-line options")
        if "\x00" in target or "\r" in target or "\n" in target:
            raise HookContractError("pytest targets contain invalid control characters")
        targets.append(target)
    return targets


def run_pytest_hook(
    request: Mapping[str, Any],
    *,
    cwd: str | Path | None = None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    """Execute one validated, bounded pytest request and return bound evidence."""
    validate_hook_request(request)
    if request["hook_id"] != PYTEST_HOOK_ID or request["action"] != PYTEST_ACTION:
        raise HookContractError("request is not for the bounded pytest adapter")
    payload = request["payload"]
    if set(payload) != {"targets"}:
        raise HookContractError("pytest payload must contain only targets")
    targets = _validate_targets(payload["targets"])
    if type(timeout_seconds) not in {int, float} or timeout_seconds <= 0 or timeout_seconds > 600:
        raise HookContractError("timeout_seconds must be greater than 0 and at most 600")

    command = [sys.executable, "-m", "pytest", "-q", *targets]
    try:
        completed = subprocess.run(
            command,
            cwd=str(Path(cwd).resolve()) if cwd is not None else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=float(timeout_seconds),
            shell=False,
        )
    except FileNotFoundError as exc:
        return build_hook_result(
            request=request,
            status="UNAVAILABLE",
            evidence={"kind": "pytest_process", "error": type(exc).__name__},
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return build_hook_result(
            request=request,
            status="FAILED",
            evidence={
                "kind": "pytest_process",
                "timed_out": True,
                "stdout": stdout[-MAX_OUTPUT_CHARS:],
                "stderr": stderr[-MAX_OUTPUT_CHARS:],
            },
        )

    evidence = {
        "kind": "pytest_process",
        "targets": targets,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-MAX_OUTPUT_CHARS:],
        "stderr": completed.stderr[-MAX_OUTPUT_CHARS:],
        "timed_out": False,
    }
    return build_hook_result(
        request=request,
        status="OBSERVED" if completed.returncode == 0 else "FAILED",
        evidence=evidence,
    )
