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
ALLOWED_ACTION = "read_text"
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


def execute_observation(
    *,
    request: Mapping[str, Any],
    allowed_root: str | Path,
) -> dict[str, Any]:
    """Execute one validated ``read_text`` request inside ``allowed_root``.

    Missing or unreadable in-root targets produce evidence-bearing hook
    results.  Invalid contracts and boundary violations fail closed.
    """
    validate_hook_request(request)

    if request["action"] != ALLOWED_ACTION:
        raise ComputerObserverError(
            f"action {request['action']!r} is not allowed"
        )

    payload = request["payload"]
    if set(payload) != {"encoding"}:
        raise ComputerObserverError(
            "read_text payload must contain only encoding"
        )
    if payload["encoding"] != ALLOWED_ENCODING:
        raise ComputerObserverError("only utf-8 text observation is allowed")

    reference = request["reference"]
    target = _resolve_allowed_target(
        reference=reference,
        allowed_root=Path(allowed_root),
    )

    try:
        resolved_target = target.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError):
        return build_hook_result(
            request=request,
            status="UNAVAILABLE",
            evidence={
                "operation": ALLOWED_ACTION,
                "reference": reference,
                "reason": "target is unavailable",
            },
        )

    root = Path(allowed_root).resolve(strict=True)
    if not resolved_target.is_relative_to(root):
        raise ComputerObserverError("reference escapes allowed root")
    if not resolved_target.is_file():
        return build_hook_result(
            request=request,
            status="UNAVAILABLE",
            evidence={
                "operation": ALLOWED_ACTION,
                "reference": reference,
                "reason": "target is not a regular file",
            },
        )

    try:
        size = resolved_target.stat().st_size
        if size > MAX_TEXT_BYTES:
            raise ComputerObserverError(
                f"target exceeds {MAX_TEXT_BYTES} byte observation limit"
            )
        data = resolved_target.read_bytes()
    except ComputerObserverError:
        raise
    except OSError:
        return build_hook_result(
            request=request,
            status="FAILED",
            evidence={
                "operation": ALLOWED_ACTION,
                "reference": reference,
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
                "operation": ALLOWED_ACTION,
                "reference": reference,
                "reason": "target is not valid utf-8",
            },
        )

    return build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={
            "operation": ALLOWED_ACTION,
            "reference": reference,
            "encoding": ALLOWED_ENCODING,
            "content": content,
            "byte_count": len(data),
            "content_sha256": hashlib.sha256(data).hexdigest(),
        },
    )