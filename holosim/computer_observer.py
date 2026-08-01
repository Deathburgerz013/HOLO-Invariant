"""Bounded, read-only computer observations through hook contracts.

This module is an execution boundary, not a general shell.  It performs one
allowlisted observation inside an explicitly supplied root and binds measured
evidence to the validated request that caused it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from holosim.hook_contract import (
    build_hook_result,
    validate_hook_request,
)


MAX_TEXT_BYTES = 1024 * 1024
MAX_RETURNED_ENTRIES = 256
MAX_SCANNED_ENTRIES = 4096
ALLOWED_ACTIONS = frozenset({"read_text", "list_directory"})
ALLOWED_ENCODING = "utf-8"


class ComputerObserverError(ValueError):
    """Raised when a requested observation exceeds its declared boundary."""


def _resolve_allowed_target(*, reference: str, allowed_root: Path) -> Path:
    try:
        root = allowed_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ComputerObserverError("allowed root is unavailable") from exc

    if not root.is_dir():
        raise ComputerObserverError("allowed root must be a directory")

    relative = Path(reference)
    if relative.is_absolute():
        raise ComputerObserverError("reference must stay inside allowed root")

    try:
        candidate = (root / relative).resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ComputerObserverError(
            "reference could not be resolved inside allowed root"
        ) from exc

    if not candidate.is_relative_to(root):
        raise ComputerObserverError("reference escapes allowed root")

    return candidate


def _unavailable_result(
    *,
    request: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    return build_hook_result(
        request=request,
        status="UNAVAILABLE",
        evidence={
            "operation": request["action"],
            "reference": request["reference"],
            "reason": reason,
        },
    )


def _read_text(
    *,
    request: Mapping[str, Any],
    target: Path,
) -> dict[str, Any]:
    if not target.is_file():
        return _unavailable_result(
            request=request,
            reason="target is not a regular file",
        )

    try:
        size = target.stat().st_size
        if size > MAX_TEXT_BYTES:
            raise ComputerObserverError(
                f"target exceeds {MAX_TEXT_BYTES} byte observation limit"
            )
        data = target.read_bytes()
    except ComputerObserverError:
        raise
    except OSError:
        return build_hook_result(
            request=request,
            status="FAILED",
            evidence={
                "operation": "read_text",
                "reference": request["reference"],
                "reason": "target could not be read",
            },
        )

    if len(data) > MAX_TEXT_BYTES:
        raise ComputerObserverError(
            f"target exceeds {MAX_TEXT_BYTES} byte observation limit"
        )

    try:
        content = data.decode(ALLOWED_ENCODING)
    except UnicodeDecodeError:
        return build_hook_result(
            request=request,
            status="FAILED",
            evidence={
                "operation": "read_text",
                "reference": request["reference"],
                "reason": "target is not valid utf-8",
            },
        )

    return build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={
            "operation": "read_text",
            "reference": request["reference"],
            "encoding": ALLOWED_ENCODING,
            "content": content,
            "byte_count": len(data),
            "content_sha256": hashlib.sha256(data).hexdigest(),
        },
    )


def _list_directory(
    *,
    request: Mapping[str, Any],
    target: Path,
) -> dict[str, Any]:
    if not target.is_dir():
        return _unavailable_result(
            request=request,
            reason="target is not a directory",
        )

    max_entries = request["payload"]["max_entries"]
    if (
        isinstance(max_entries, bool)
        or not isinstance(max_entries, int)
        or not 1 <= max_entries <= MAX_RETURNED_ENTRIES
    ):
        raise ComputerObserverError(
            f"max_entries must be an integer from 1 to {MAX_RETURNED_ENTRIES}"
        )

    scanned: list[Path] = []
    try:
        for child in target.iterdir():
            scanned.append(child)
            if len(scanned) > MAX_SCANNED_ENTRIES:
                raise ComputerObserverError(
                    "directory exceeds bounded scan limit"
                )
    except ComputerObserverError:
        raise
    except OSError:
        return build_hook_result(
            request=request,
            status="FAILED",
            evidence={
                "operation": "list_directory",
                "reference": request["reference"],
                "reason": "directory could not be listed",
            },
        )

    entries: list[dict[str, str]] = []
    for child in sorted(scanned, key=lambda item: item.name)[:max_entries]:
        if child.is_symlink():
            kind = "symlink"
        elif child.is_file():
            kind = "file"
        elif child.is_dir():
            kind = "directory"
        else:
            kind = "other"
        entries.append({"name": child.name, "kind": kind})

    return build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={
            "operation": "list_directory",
            "reference": request["reference"],
            "entries": entries,
            "entry_count": len(scanned),
            "truncated": len(scanned) > max_entries,
        },
    )


def execute_observation(
    *,
    request: Mapping[str, Any],
    allowed_root: str | Path,
) -> dict[str, Any]:
    """Execute one validated, allowlisted request inside ``allowed_root``.

    Missing or unreadable in-root targets produce evidence-bearing hook
    results.  Invalid contracts and boundary violations fail closed.
    """
    validate_hook_request(request)

    if request["action"] not in ALLOWED_ACTIONS:
        raise ComputerObserverError(
            f"action {request['action']!r} is not allowed"
        )

    payload = request["payload"]
    if request["action"] == "read_text":
        if set(payload) != {"encoding"}:
            raise ComputerObserverError(
                "read_text payload must contain only encoding"
            )
        if payload["encoding"] != ALLOWED_ENCODING:
            raise ComputerObserverError(
                "only utf-8 text observation is allowed"
            )
    elif set(payload) != {"max_entries"}:
        raise ComputerObserverError(
            "list_directory payload must contain only max_entries"
        )

    reference = request["reference"]
    target = _resolve_allowed_target(
        reference=reference,
        allowed_root=Path(allowed_root),
    )

    try:
        resolved_target = target.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError):
        return _unavailable_result(
            request=request,
            reason="target is unavailable",
        )

    root = Path(allowed_root).resolve(strict=True)
    if not resolved_target.is_relative_to(root):
        raise ComputerObserverError("reference escapes allowed root")
    if request["action"] == "read_text":
        return _read_text(request=request, target=resolved_target)
    return _list_directory(request=request, target=resolved_target)
