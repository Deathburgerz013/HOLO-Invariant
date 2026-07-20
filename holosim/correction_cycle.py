"""Bounded, read-only correction-cycle observations for Holo/Sim.

The cycle consumes validated reconstruction manifests in order. It exposes only
explicit changed or missing IDs as correction targets and stops at the first
manifest with no relevant difference. It never mutates state, invents a
correction, grants acceptance, or grants write authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .reconstructor import (
    RECONSTRUCTION_VERSION,
    ReconstructionError,
    validate_reconstruction_manifest,
)

CORRECTION_CYCLE_TYPE = "holo_correction_cycle"
CORRECTION_CYCLE_VERSION = 1
MAX_CYCLE_STEPS = 10_000


class CorrectionCycleError(ValueError):
    """Raised when correction-cycle inputs are malformed or inconsistent."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise CorrectionCycleError(f"{field} must be a nonempty plain string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise CorrectionCycleError(f"{field} must be valid UTF-8") from exc
    return value


def _digest(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise CorrectionCycleError("cycle could not be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def _targets(manifest: Mapping[str, Any]) -> list[str]:
    changed = manifest["changed"]
    missing = manifest["missing_ids"]
    ids = {entry["id"] for entry in changed}
    ids.update(missing)
    return sorted(ids)


def build_correction_cycle(
    reference: str,
    manifests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Observe successive reconstruction deltas until none remain.

    Only ``changed`` and ``missing_ids`` are relevant correction targets.
    ``added_ids`` represent environmental growth and do not keep the correction
    cycle open by themselves.
    """
    checked_reference = _text(reference, "reference")
    if type(manifests) not in {list, tuple}:
        raise CorrectionCycleError("manifests must be a list or tuple")
    if not manifests:
        raise CorrectionCycleError("manifests must not be empty")
    if len(manifests) > MAX_CYCLE_STEPS:
        raise CorrectionCycleError("manifests exceed maximum cycle steps")

    steps: list[dict[str, Any]] = []
    terminal_index: int | None = None

    for index, manifest in enumerate(manifests):
        try:
            validate_reconstruction_manifest(manifest)
        except ReconstructionError as exc:
            raise CorrectionCycleError(
                f"manifests[{index}] is not a valid reconstruction manifest"
            ) from exc
        if manifest["version"] != RECONSTRUCTION_VERSION:
            raise CorrectionCycleError("reconstruction manifest version is unsupported")
        if manifest["reference"] != checked_reference:
            raise CorrectionCycleError("all manifests must use the cycle reference")

        targets = _targets(manifest)
        step_status = "CORRECTION_REQUIRED" if targets else "NO_RELEVANT_DIFFERENCE"
        steps.append(
            {
                "index": index,
                "reconstruction_hash": manifest["reconstruction_hash"],
                "correction_targets": targets,
                "status": step_status,
            }
        )
        if not targets:
            terminal_index = index
            break

    if terminal_index is None:
        status = "CORRECTION_REQUIRED"
        next_targets = list(steps[-1]["correction_targets"])
        unprocessed_count = 0
    else:
        status = "NO_RELEVANT_DIFFERENCE"
        next_targets = []
        unprocessed_count = len(manifests) - terminal_index - 1

    body: dict[str, Any] = {
        "type": CORRECTION_CYCLE_TYPE,
        "version": CORRECTION_CYCLE_VERSION,
        "reference": checked_reference,
        "steps": steps,
        "processed_step_count": len(steps),
        "unprocessed_after_terminal_count": unprocessed_count,
        "terminal_index": terminal_index,
        "next_correction_targets": next_targets,
        "status": status,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Correction cycles expose explicit reconstruction differences only. "
            "They do not choose or apply corrections, establish truth, acceptance, "
            "or authority. Added environmental state alone does not keep a cycle open."
        ),
    }
    return {**body, "cycle_hash": _digest(body)}


def validate_correction_cycle(cycle: Mapping[str, Any]) -> bool:
    """Fail closed unless a correction-cycle observation is self-consistent."""
    if type(cycle) is not dict:
        raise CorrectionCycleError("cycle must be a plain dictionary")
    expected = {
        "type", "version", "reference", "steps", "processed_step_count",
        "unprocessed_after_terminal_count", "terminal_index",
        "next_correction_targets", "status", "accepted", "write_authority",
        "interpretation_notice", "cycle_hash",
    }
    if set(cycle) != expected:
        raise CorrectionCycleError("cycle fields do not match the versioned schema")
    if cycle["type"] != CORRECTION_CYCLE_TYPE or cycle["version"] != CORRECTION_CYCLE_VERSION:
        raise CorrectionCycleError("cycle type or version is invalid")
    _text(cycle["reference"], "reference")
    if cycle["accepted"] is not False or cycle["write_authority"] != "NONE":
        raise CorrectionCycleError("correction cycle cannot grant acceptance or authority")
    if type(cycle["steps"]) is not list or not cycle["steps"]:
        raise CorrectionCycleError("steps must be a nonempty list")
    if cycle["processed_step_count"] != len(cycle["steps"]):
        raise CorrectionCycleError("processed_step_count is inconsistent with steps")
    if type(cycle["unprocessed_after_terminal_count"]) is not int or cycle["unprocessed_after_terminal_count"] < 0:
        raise CorrectionCycleError("unprocessed_after_terminal_count is invalid")

    saw_terminal = False
    for index, step in enumerate(cycle["steps"]):
        if type(step) is not dict or set(step) != {
            "index", "reconstruction_hash", "correction_targets", "status"
        }:
            raise CorrectionCycleError("step fields are invalid")
        if step["index"] != index:
            raise CorrectionCycleError("step indexes must be ordered")
        digest = step["reconstruction_hash"]
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CorrectionCycleError("step reconstruction_hash is invalid")
        targets = step["correction_targets"]
        if type(targets) is not list or any(type(value) is not str or not value for value in targets):
            raise CorrectionCycleError("correction_targets must be nonempty strings")
        if targets != sorted(set(targets)):
            raise CorrectionCycleError("correction_targets must be sorted and unique")
        expected_status = "CORRECTION_REQUIRED" if targets else "NO_RELEVANT_DIFFERENCE"
        if step["status"] != expected_status:
            raise CorrectionCycleError("step status is inconsistent with correction targets")
        if saw_terminal:
            raise CorrectionCycleError("steps cannot continue after terminal state")
        if not targets:
            saw_terminal = True

    terminal_index = cycle["terminal_index"]
    if saw_terminal:
        if terminal_index != len(cycle["steps"]) - 1:
            raise CorrectionCycleError("terminal_index must identify the terminal step")
        if cycle["status"] != "NO_RELEVANT_DIFFERENCE":
            raise CorrectionCycleError("terminal cycle status is invalid")
        if cycle["next_correction_targets"] != []:
            raise CorrectionCycleError("terminal cycle cannot expose next correction targets")
    else:
        if terminal_index is not None:
            raise CorrectionCycleError("nonterminal cycle cannot have terminal_index")
        if cycle["status"] != "CORRECTION_REQUIRED":
            raise CorrectionCycleError("nonterminal cycle status is invalid")
        if cycle["unprocessed_after_terminal_count"] != 0:
            raise CorrectionCycleError("nonterminal cycle cannot have unprocessed terminal steps")
        if cycle["next_correction_targets"] != cycle["steps"][-1]["correction_targets"]:
            raise CorrectionCycleError("next correction targets are inconsistent with final step")

    if type(cycle["interpretation_notice"]) is not str:
        raise CorrectionCycleError("interpretation_notice must be a string")
    digest = cycle["cycle_hash"]
    if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CorrectionCycleError("cycle_hash must be a SHA-256 hex digest")
    body = dict(cycle)
    body.pop("cycle_hash")
    if _digest(body) != digest:
        raise CorrectionCycleError("cycle hash mismatch")
    return True
