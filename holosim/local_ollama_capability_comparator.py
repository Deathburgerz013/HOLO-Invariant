"""Bounded local-model comparison of one capability and workspace."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash
from holosim.local_ollama_adapter import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    LocalOllamaAdapterError,
    request_local_ollama_json,
)


DEFAULT_MAX_FILES = 32
DEFAULT_MAX_TOTAL_BYTES = 65_536
_IGNORED_PARTS = {".git", ".venv", "__pycache__"}


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise LocalOllamaAdapterError(f"{field} must be a positive integer")
    return value


def _workspace_snapshot(
    workspace: Path,
    *,
    max_files: int,
    max_total_bytes: int,
) -> dict[str, Any]:
    root = workspace.resolve()
    if not root.is_dir():
        raise LocalOllamaAdapterError("workspace must be an existing directory")

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    candidates = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not any(part in _IGNORED_PARTS for part in path.parts)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    truncated = len(candidates) > max_files

    for path in candidates[:max_files]:
        raw = path.read_bytes()
        if total_bytes + len(raw) > max_total_bytes:
            truncated = True
            break
        total_bytes += len(raw)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = None
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "byte_count": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "utf8_content": content,
            }
        )

    body = {
        "files": entries,
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "truncated": truncated,
    }
    return {**body, "snapshot_hash": stable_hash(body)}


class LocalOllamaCapabilityComparator:
    """Compare one goal against bounded observable workspace evidence."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 120.0,
        max_files: int = DEFAULT_MAX_FILES,
        max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
        requester: Callable[..., Mapping[str, Any]] = (
            request_local_ollama_json
        ),
    ) -> None:
        if not callable(requester):
            raise TypeError("requester must be callable")
        self._model = model
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._max_files = _positive_int(max_files, "max_files")
        self._max_total_bytes = _positive_int(
            max_total_bytes,
            "max_total_bytes",
        )
        self._requester = requester
        self.last_receipt: dict[str, Any] | None = None

    def __call__(self, goal: Any, workspace: Path) -> dict[str, Any]:
        snapshot = _workspace_snapshot(
            Path(workspace),
            max_files=self._max_files,
            max_total_bytes=self._max_total_bytes,
        )
        if snapshot["file_count"] == 0:
            return {
                "relevant_difference": True,
                "reason": "WORKSPACE_EMPTY",
                "description": {
                    "goal": deepcopy(goal),
                    "observations": [
                        "No workspace files exist for the requested capability"
                    ],
                    "workspace_snapshot_hash": snapshot["snapshot_hash"],
                },
                "workspace_snapshot": snapshot,
                "model_generated": False,
                "verified": False,
                "accepted": False,
                "write_authority": "NONE",
                "execution_authority": "NONE",
            }
        prompt = json.dumps(
            {
                "task": "compare_capability_to_workspace",
                "instruction": (
                    "Return only the JSON object matching output_schema. "
                    "Report whether a concrete implementation difference "
                    "remains. Do not claim verification or acceptance."
                ),
                "goal": deepcopy(goal),
                "workspace_snapshot": snapshot,
                "output_schema": {
                    "relevant_difference": True,
                    "reason": "non-empty bounded reason",
                    "observations": ["evidence-grounded observation"],
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        receipt = self._requester(
            prompt,
            model=self._model,
            endpoint=self._endpoint,
            timeout_seconds=self._timeout_seconds,
        )
        if not isinstance(receipt, Mapping):
            raise LocalOllamaAdapterError("requester must return a mapping")
        output = receipt.get("output")
        if not isinstance(output, Mapping):
            raise LocalOllamaAdapterError("receipt output must be a mapping")

        relevant_difference = output.get("relevant_difference")
        reason = output.get("reason")
        observations = output.get("observations")
        if not isinstance(relevant_difference, bool):
            raise LocalOllamaAdapterError(
                "relevant_difference must be a boolean"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise LocalOllamaAdapterError("reason must be a non-empty string")
        if (
            not isinstance(observations, list)
            or any(
                not isinstance(item, str) or not item.strip()
                for item in observations
            )
        ):
            raise LocalOllamaAdapterError(
                "observations must be a list of non-empty strings"
            )

        self.last_receipt = deepcopy(dict(receipt))
        return {
            "relevant_difference": relevant_difference,
            "reason": reason.strip(),
            "description": {
                "goal": deepcopy(goal),
                "observations": deepcopy(observations),
                "workspace_snapshot_hash": snapshot["snapshot_hash"],
            },
            "workspace_snapshot": snapshot,
            "model_generated": True,
            "verified": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }


def build_local_ollama_capability_comparator(
    **kwargs: Any,
) -> LocalOllamaCapabilityComparator:
    """Build one comparator injectable for the convergence loop."""
    return LocalOllamaCapabilityComparator(**kwargs)
