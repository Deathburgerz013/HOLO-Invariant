"""Bounded software-building orchestration for HOLO/Sim.

The builder owns only the observe -> propose -> apply -> verify loop.

Proposal generation and verification are injected by the caller.
The builder grants no truth, acceptance, or write authority.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "software_builder_cycle_receipt"
RECEIPT_VERSION = 1
DEFAULT_MAX_ATTEMPTS = 3


def _observe_workspace(workspace: Path) -> dict[str, Any]:
    """Return a deterministic content observation of a workspace."""
    workspace = workspace.resolve()

    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")

    files: dict[str, dict[str, Any]] = {}

    for path in sorted(
        (path for path in workspace.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(workspace).as_posix(),
    ):
        relative_path = path.relative_to(workspace).as_posix()
        content = path.read_bytes()

        files[relative_path] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }

    observation = {"files": files}

    return {
        "files": files,
        "workspace_hash": stable_hash(observation),
    }


def _resolve_bounded_path(workspace: Path, relative_path: str) -> Path:
    """Resolve a proposed path and reject writes outside the workspace."""
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("proposed file path must be a non-empty string")

    candidate_path = Path(relative_path)

    if candidate_path.is_absolute():
        raise ValueError(
            f"absolute proposed path is not allowed: {relative_path!r}"
        )

    target = (workspace / candidate_path).resolve()

    try:
        target.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(
            f"proposed path escapes workspace: {relative_path!r}"
        ) from exc

    return target


def _apply_bounded_changes(
    workspace: Path,
    changes: Mapping[str, Any],
) -> list[str]:
    """Apply explicit file writes only inside the supplied workspace."""
    if not isinstance(changes, Mapping):
        raise TypeError(
            "proposer changes must be a mapping of relative paths to contents"
        )

    applied: list[str] = []

    for relative_path, content in changes.items():
        target = _resolve_bounded_path(workspace, relative_path)

        target.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            target.write_bytes(content)
        elif isinstance(content, str):
            target.write_text(content, encoding="utf-8")
        else:
            raise TypeError(
                f"proposed content for {relative_path!r} must be str or bytes"
            )

        applied.append(target.relative_to(workspace).as_posix())

    return sorted(applied)


def run_software_builder_cycle(
    task: Any,
    workspace: str | Path,
    proposer: Callable[..., Mapping[str, Any]],
    verifier: Callable[[Path], Mapping[str, Any]],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    environmental_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a bounded propose -> apply -> verify software-building cycle."""
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
        raise TypeError("max_attempts must be an integer")

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    workspace_path = Path(workspace).resolve()

    if not workspace_path.is_dir():
        raise ValueError("workspace must be an existing directory")

    constraints = deepcopy(dict(environmental_constraints or {}))
    observed_starting_state = _observe_workspace(workspace_path)

    attempts: list[dict[str, Any]] = []
    files_changed: set[str] = set()
    feedback_received: list[Any] = []
    corrections_made: list[dict[str, Any]] = []

    prior_feedback: Any = None
    final_verification_state: dict[str, Any] | None = None

    for attempt_number in range(1, max_attempts + 1):
        proposal = proposer(
            task,
            deepcopy(observed_starting_state),
            deepcopy(constraints),
            deepcopy(prior_feedback),
        )

        if not isinstance(proposal, Mapping):
            raise TypeError("proposer must return a mapping")

        proposed_files = proposal.get("files")

        if not isinstance(proposed_files, Mapping):
            raise TypeError(
                "proposer result must contain a 'files' mapping"
            )

        applied_files = _apply_bounded_changes(
            workspace_path,
            proposed_files,
        )
        files_changed.update(applied_files)

        verification = verifier(workspace_path)

        if not isinstance(verification, Mapping):
            raise TypeError("verifier must return a mapping")

        verification_record = deepcopy(dict(verification))
        passed = verification_record.get("passed") is True

        attempt_record = {
            "attempt": attempt_number,
            "proposal": deepcopy(dict(proposal)),
            "files_applied": applied_files,
            "feedback_used": deepcopy(prior_feedback),
            "verification": verification_record,
        }
        attempts.append(attempt_record)

        final_verification_state = verification_record

        if passed:
            break

        prior_feedback = deepcopy(
            verification_record.get(
                "feedback",
                verification_record.get("message", verification_record),
            )
        )

        feedback_received.append(deepcopy(prior_feedback))

        corrections_made.append(
            {
                "after_attempt": attempt_number,
                "feedback": deepcopy(prior_feedback),
            }
        )

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "task": deepcopy(task),
        "observed_starting_state": observed_starting_state,
        "environmental_constraints": constraints,
        "attempts": attempts,
        "files_changed": sorted(files_changed),
        "verification_results": [
            deepcopy(attempt["verification"])
            for attempt in attempts
        ],
        "feedback_received": feedback_received,
        "corrections_made": corrections_made,
        "final_verification_state": final_verification_state,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }