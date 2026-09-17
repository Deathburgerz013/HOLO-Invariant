"""Read-only diagnosis for malformed HoloChain terminal records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

TYPE = "holochain_terminal_tail_diagnosis"
VERSION = 1

STATUS_CLEAN = "CLEAN"
STATUS_TERMINAL_INVALID_RECORD = "TERMINAL_INVALID_RECORD"
STATUS_INTERIOR_INTEGRITY_FAILURE = "INTERIOR_INTEGRITY_FAILURE"

FAILURE_INVALID_UTF8 = "INVALID_UTF8"
FAILURE_INVALID_JSON = "INVALID_JSON"
FAILURE_MISSING_FIELD = "MISSING_FIELD"
FAILURE_INVALID_ENTRY = "INVALID_ENTRY"
FAILURE_HASH_MISMATCH = "HASH_MISMATCH"
FAILURE_INDEX_NOT_MONOTONIC = "INDEX_NOT_MONOTONIC"

_NOTICE = (
    "Diagnosis is a read-only structural observation. A terminal invalid "
    "record is consistent with an interrupted write but does not prove its "
    "cause. No bytes are truncated, repaired, accepted, or authorized."
)


def _failure_kind(exc: Exception) -> str:
    if isinstance(exc, UnicodeDecodeError):
        return FAILURE_INVALID_UTF8
    if isinstance(exc, json.JSONDecodeError):
        return FAILURE_INVALID_JSON
    if isinstance(exc, KeyError):
        return FAILURE_MISSING_FIELD
    if isinstance(exc, (TypeError, AttributeError)):
        return FAILURE_INVALID_ENTRY
    return FAILURE_INVALID_ENTRY


def _compute_hash(
    prev_hash: str,
    content: str,
    timestamp: str,
    idx: int,
) -> str:
    canonical = json.dumps(
        {
            "idx": idx,
            "timestamp": timestamp,
            "content": content,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(prev_hash.encode() + canonical.encode()).hexdigest()


def _receipt(
    *,
    source_exists: bool,
    source_sha256: str,
    byte_count: int,
    terminal_newline_present: bool,
    status: str,
    complete_entry_count: int,
    failure_line: int | None,
    failure_kind: str | None,
) -> dict[str, Any]:
    return {
        "type": TYPE,
        "version": VERSION,
        "source_exists": source_exists,
        "source_sha256": source_sha256,
        "byte_count": byte_count,
        "terminal_newline_present": terminal_newline_present,
        "status": status,
        "complete_entry_count": complete_entry_count,
        "failure_line": failure_line,
        "failure_kind": failure_kind,
        "repair_performed": False,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": _NOTICE,
    }


def diagnose_holochain_terminal_tail(
    file_path: str | Path,
    *,
    genesis_hash: str = "0" * 64,
) -> dict[str, Any]:
    """Classify the first chain failure without modifying the source file."""
    path = Path(file_path)
    source_exists = path.exists()
    raw = path.read_bytes() if source_exists else b""
    source_sha256 = hashlib.sha256(raw).hexdigest()
    physical_lines = raw.splitlines(keepends=True)
    nonempty_lines = [
        line_number
        for line_number, line in enumerate(physical_lines, 1)
        if line.strip()
    ]
    last_nonempty_line = nonempty_lines[-1] if nonempty_lines else None

    prev_hash = genesis_hash
    complete_entry_count = 0

    for line_number, encoded_line in enumerate(physical_lines, 1):
        encoded_line = encoded_line.strip()
        if not encoded_line:
            continue

        try:
            entry = json.loads(encoded_line.decode("utf-8"))
            expected_hash = _compute_hash(
                prev_hash,
                entry["content"],
                entry["timestamp"],
                entry["idx"],
            )
            if (
                entry["hash"] != expected_hash
                or entry.get("prev_hash") != prev_hash
            ):
                failure_kind = FAILURE_HASH_MISMATCH
            elif entry["idx"] != complete_entry_count + 1:
                failure_kind = FAILURE_INDEX_NOT_MONOTONIC
            else:
                prev_hash = entry["hash"]
                complete_entry_count += 1
                continue
        except Exception as exc:
            failure_kind = _failure_kind(exc)

        status = (
            STATUS_TERMINAL_INVALID_RECORD
            if line_number == last_nonempty_line
            else STATUS_INTERIOR_INTEGRITY_FAILURE
        )
        return _receipt(
            source_exists=source_exists,
            source_sha256=source_sha256,
            byte_count=len(raw),
            terminal_newline_present=raw.endswith(b"\n"),
            status=status,
            complete_entry_count=complete_entry_count,
            failure_line=line_number,
            failure_kind=failure_kind,
        )

    return _receipt(
        source_exists=source_exists,
        source_sha256=source_sha256,
        byte_count=len(raw),
        terminal_newline_present=raw.endswith(b"\n"),
        status=STATUS_CLEAN,
        complete_entry_count=complete_entry_count,
        failure_line=None,
        failure_kind=None,
    )
