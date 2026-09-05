"""Read-only, revision-bound observation of exact-path Git origins."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any


RECEIPT_TYPE = "repository_observed_genesis_origin_receipt"
RECEIPT_VERSION = 1
_OBJECT_ID = re.compile(r"[0-9a-f]{40,64}")
_FIELDS = {
    "type", "version", "path", "requested_revision", "head_commit",
    "head_blob", "addition_events", "genesis_candidates", "status",
    "rename_followed", "all_refs_searched", "accepted", "write_authority",
    "interpretation_notice", "receipt_hash",
}


class GenesisOriginError(ValueError):
    """Raised when an exact-path origin cannot be observed honestly."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise GenesisOriginError("origin receipt could not be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise GenesisOriginError("path must be a portable relative path")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or candidate.as_posix() in {"", "."}:
        raise GenesisOriginError("path must stay inside the repository")
    return candidate.as_posix()


def _revision(value: Any) -> str:
    if not isinstance(value, str) or not value or value.startswith("-"):
        raise GenesisOriginError("revision is invalid")
    if any(character.isspace() or character == "\x00" for character in value):
        raise GenesisOriginError("revision is invalid")
    return value


def _git(root: Path, *arguments: str, allow_absent: bool = False) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise GenesisOriginError("Git observation failed") from exc
    if result.returncode != 0:
        if allow_absent:
            return None
        raise GenesisOriginError("Git observation failed")
    return result.stdout.strip()


def _object_id(value: str | None, label: str) -> str:
    if value is None or _OBJECT_ID.fullmatch(value) is None:
        raise GenesisOriginError(f"{label} is not a full Git object ID")
    return value


def _commit_record(root: Path, commit: str, path: str) -> dict[str, Any]:
    parents_raw = _git(root, "show", "-s", "--format=%P", commit)
    parents = [] if not parents_raw else parents_raw.split()
    if any(_OBJECT_ID.fullmatch(parent) is None for parent in parents):
        raise GenesisOriginError("parent object ID is invalid")
    blob = _object_id(
        _git(root, "rev-parse", f"{commit}:{path}"), "blob object ID"
    )
    return {"commit": commit, "parents": parents, "blob": blob}


def observe_repository_path_genesis(
    *, root: str | Path, path: str, revision: str = "HEAD"
) -> dict[str, Any]:
    """Observe exact-path additions reachable from one pinned Git revision."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise GenesisOriginError("repository root is unavailable")
    top = _git(root_path, "rev-parse", "--show-toplevel")
    if top is None or Path(top).resolve() != root_path:
        raise GenesisOriginError("root is not the Git worktree root")
    normalized_path = _path(path)
    requested_revision = _revision(revision)
    head = _object_id(
        _git(root_path, "rev-parse", f"{requested_revision}^{{commit}}"),
        "head commit",
    )
    head_blob = _object_id(
        _git(root_path, "rev-parse", f"{head}:{normalized_path}"),
        "head blob",
    )
    additions_raw = _git(
        root_path,
        "log", "--format=%H", "--diff-filter=A", head, "--", normalized_path,
    )
    additions = sorted(set(additions_raw.splitlines() if additions_raw else []))
    if not additions or any(_OBJECT_ID.fullmatch(item) is None for item in additions):
        raise GenesisOriginError("no exact-path addition is reachable")

    genesis = []
    for candidate in additions:
        has_addition_ancestor = False
        for other in additions:
            if other == candidate:
                continue
            relation = subprocess.run(
                ["git", "merge-base", "--is-ancestor", other, candidate],
                cwd=root_path, check=False, capture_output=True, timeout=30,
            )
            if relation.returncode not in {0, 1}:
                raise GenesisOriginError("Git ancestry observation failed")
            if relation.returncode == 0:
                has_addition_ancestor = True
                break
        if not has_addition_ancestor:
            genesis.append(candidate)

    records = [_commit_record(root_path, commit, normalized_path) for commit in additions]
    genesis_set = set(genesis)
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "path": normalized_path,
        "requested_revision": requested_revision,
        "head_commit": head,
        "head_blob": head_blob,
        "addition_events": records,
        "genesis_candidates": [item for item in records if item["commit"] in genesis_set],
        "status": "UNIQUE" if len(genesis) == 1 else "AMBIGUOUS",
        "rename_followed": False,
        "all_refs_searched": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Genesis means the earliest reachable addition of this exact path under "
            "the pinned revision. It does not establish absolute creation, authorship, "
            "intent, rename or copy lineage, deleted refs, truth, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": _canonical_hash(body)}


def verify_genesis_origin_receipt(
    receipt: Mapping[str, Any], *, root: str | Path
) -> dict[str, Any]:
    """Re-observe a pinned origin receipt without granting authority."""
    if not isinstance(receipt, Mapping) or set(receipt) != _FIELDS:
        raise GenesisOriginError("receipt fields mismatch")
    failures: list[str] = []
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        failures.append("receipt_contract_mismatch")
    if receipt["rename_followed"] is not False or receipt["all_refs_searched"] is not False:
        failures.append("observation_scope_mismatch")
    if receipt["accepted"] is not False or receipt["write_authority"] != "NONE":
        failures.append("forbidden_authority")
    try:
        rebuilt = observe_repository_path_genesis(
            root=root, path=receipt["path"], revision=receipt["head_commit"]
        )
    except GenesisOriginError:
        rebuilt = None
        failures.append("origin_rebuild_failed")
    if rebuilt is not None:
        for field in (
            "path", "head_commit", "head_blob", "addition_events",
            "genesis_candidates", "status", "interpretation_notice",
        ):
            if receipt[field] != rebuilt[field]:
                failures.append(f"{field}_mismatch")
    body = {key: receipt[key] for key in receipt if key != "receipt_hash"}
    if receipt["receipt_hash"] != _canonical_hash(body):
        failures.append("receipt_hash_mismatch")
    result_body = {
        "type": "repository_observed_genesis_origin_check",
        "version": 1,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "path": receipt["path"],
        "head_commit": receipt["head_commit"],
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**result_body, "check_hash": _canonical_hash(result_body)}
