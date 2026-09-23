"""Fail-closed recovery of a verified HoloChain prefix.

A damaged chain may contain a valid verified prefix followed by an invalid
terminal record. This module extracts only that verified prefix into a
separate artifact.

The source artifact is never repaired or modified.

Interior integrity failures are reported but are not recovered.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .holochain_terminal_tail_diagnosis import (
    STATUS_CLEAN,
    STATUS_INTERIOR_INTEGRITY_FAILURE,
    STATUS_TERMINAL_INVALID_RECORD,
    diagnose_holochain_terminal_tail,
)


RECOVERY_TYPE = "holochain_verified_prefix_recovery"
RECOVERY_VERSION = 1


class VerifiedPrefixRecoveryError(ValueError):
    """Recovery input or output violates the recovery contract."""


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verified_head_hash(
    source: Path,
    complete_entry_count: int,
) -> str | None:
    """Return the hash of the already-verified prefix head.

    This function only reads complete entries before the diagnosed failure.
    It never treats an invalid entry as part of the verified prefix.
    """
    if complete_entry_count == 0:
        return None

    physical_lines = source.read_bytes().splitlines()

    entries_seen = 0
    head_hash: str | None = None

    for raw_line in physical_lines:
        if not raw_line.strip():
            continue

        if entries_seen >= complete_entry_count:
            break

        import json

        entry = json.loads(raw_line.decode("utf-8"))
        head_hash = entry["hash"]
        entries_seen += 1

    if entries_seen != complete_entry_count:
        raise VerifiedPrefixRecoveryError(
            "could not reconstruct the diagnosed verified prefix"
        )

    return head_hash


def _build_receipt(
    *,
    source: Path,
    recovery: Path,
    source_bytes: bytes,
    recovery_bytes: bytes | None,
    diagnosis: dict[str, Any],
    status: str,
    reason: str,
    verified_head_hash: str | None,
    corrupt_tail_preserved: bool,
) -> dict[str, Any]:
    return {
        "type": RECOVERY_TYPE,
        "version": RECOVERY_VERSION,
        "source_path": source.as_posix(),
        "recovery_path": recovery.as_posix(),
        "source_sha256": _digest_bytes(source_bytes),
        "verified_prefix_sha256": (
            _digest_bytes(recovery_bytes)
            if recovery_bytes is not None
            else None
        ),
        "source_byte_count": len(source_bytes),
        "recovery_byte_count": (
            len(recovery_bytes)
            if recovery_bytes is not None
            else 0
        ),
        "verified_entry_count": diagnosis["complete_entry_count"],
        "verified_head_hash": verified_head_hash,
        "status": status,
        "reason": reason,
        "corrupt_tail_preserved": corrupt_tail_preserved,
        "repair_performed": False,
        "source_modified": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def recover_verified_prefix(
    source_path: str | Path,
    recovery_path: str | Path | None = None,
) -> dict[str, Any]:
    """Recover a verified prefix without modifying the source.

    Terminal corruption is recoverable.

    Interior integrity failure is detected and returned without producing a
    recovery artifact, because data after the first invalid record cannot be
    promoted merely because an earlier prefix was valid.

    A clean chain can also be copied into a separate recovery artifact.
    """
    source = Path(source_path)

    if recovery_path is None:
        recovery = source.with_name(source.name + ".verified-prefix")
    else:
        recovery = Path(recovery_path)

    if source.absolute() == recovery.absolute():
        raise VerifiedPrefixRecoveryError(
            "recovery_path must differ from source_path"
        )

    if not source.exists():
        raise VerifiedPrefixRecoveryError("source chain must exist")

    if not source.is_file():
        raise VerifiedPrefixRecoveryError(
            "source chain must be a regular file"
        )

    if recovery.exists() and not recovery.is_file():
        raise VerifiedPrefixRecoveryError(
            "recovery_path must be a regular file when it exists"
        )

    source_bytes = source.read_bytes()

    diagnosis = diagnose_holochain_terminal_tail(source)
    status = diagnosis["status"]

    verified_head_hash = _verified_head_hash(
        source,
        diagnosis["complete_entry_count"],
    )

    if status == STATUS_INTERIOR_INTEGRITY_FAILURE:
        return _build_receipt(
            source=source,
            recovery=recovery,
            source_bytes=source_bytes,
            recovery_bytes=None,
            diagnosis=diagnosis,
            status=STATUS_INTERIOR_INTEGRITY_FAILURE,
            reason="INTERIOR_INTEGRITY_FAILURE",
            verified_head_hash=verified_head_hash,
            corrupt_tail_preserved=False,
        )

    if status not in {
        STATUS_TERMINAL_INVALID_RECORD,
        STATUS_CLEAN,
    }:
        raise VerifiedPrefixRecoveryError(
            f"unexpected terminal diagnosis status: {status!r}"
        )

    physical_lines = source_bytes.splitlines(keepends=True)
    failure_line = diagnosis["failure_line"]

    if failure_line is None:
        verified_lines = physical_lines
    else:
        # failure_line is one-based, so all preceding lines are the
        # diagnosed verified prefix.
        verified_lines = physical_lines[: failure_line - 1]

    recovery_bytes = b"".join(verified_lines)

    recovery.parent.mkdir(parents=True, exist_ok=True)
    recovery.write_bytes(recovery_bytes)

    persisted_recovery_bytes = recovery.read_bytes()

    if _digest_bytes(persisted_recovery_bytes) != _digest_bytes(
        recovery_bytes
    ):
        raise VerifiedPrefixRecoveryError(
            "recovery artifact changed after writing"
        )

    from .core import HoloChain

    recovered_chain = HoloChain(recovery)
    entries = recovered_chain.load_and_verify()

    if len(entries) != diagnosis["complete_entry_count"]:
        raise VerifiedPrefixRecoveryError(
            "recovered entry count does not match verified prefix"
        )

    recovered_head_hash = entries[-1]["hash"] if entries else None

    if recovered_head_hash != verified_head_hash:
        raise VerifiedPrefixRecoveryError(
            "recovered head hash does not match diagnosed verified head"
        )

    if source.read_bytes() != source_bytes:
        raise VerifiedPrefixRecoveryError(
            "source chain changed during prefix recovery"
        )

    return _build_receipt(
        source=source,
        recovery=recovery,
        source_bytes=source_bytes,
        recovery_bytes=persisted_recovery_bytes,
        diagnosis=diagnosis,
        status="RECOVERED_PREFIX",
        reason="VERIFIED_PREFIX_EXTRACTED_WITHOUT_SOURCE_MUTATION",
        verified_head_hash=recovered_head_hash,
        corrupt_tail_preserved=(
            status == STATUS_TERMINAL_INVALID_RECORD
        ),
    )