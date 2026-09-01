"""Verified, fail-closed recovery for one stopped on-disk artifact.

Recovery requires independently supplied expected bytes.  A digest detects
identity; it cannot reconstruct missing information.  This module never edits
live process memory, invents replacement bytes, or grants execution authority.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .canonical import stable_hash


RECOVERY_TYPE = "holo_verified_artifact_recovery_receipt"
RECOVERY_VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}")


class VerifiedArtifactRecoveryError(ValueError):
    """Recovery input or a stored receipt violates the closed contract."""


def _digest(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                hasher.update(block)
                size += len(block)
    except OSError as exc:
        raise VerifiedArtifactRecoveryError(
            f"unable to read artifact: {path}"
        ) from exc
    return hasher.hexdigest(), size


def _regular_file(path: Path, label: str, *, may_be_missing: bool = False) -> None:
    if path.is_symlink():
        raise VerifiedArtifactRecoveryError(f"{label} must not be a symbolic link")
    if not path.exists():
        if may_be_missing:
            return
        raise VerifiedArtifactRecoveryError(f"{label} must exist")
    if not path.is_file():
        raise VerifiedArtifactRecoveryError(f"{label} must be a regular file")


def _receipt(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "receipt_hash": stable_hash(body)}


def _body(
    *,
    target: Path,
    trusted_source: Path,
    expected_sha256: str,
    observed_sha256: str | None,
    recovered_sha256: str | None,
    artifact_size_bytes: int | None,
    quarantine_path: Path | None,
    status: str,
    reason: str,
    mutation_applied: bool,
) -> dict[str, Any]:
    return {
        "type": RECOVERY_TYPE,
        "version": RECOVERY_VERSION,
        "target_path": target.as_posix(),
        "trusted_source_path": trusted_source.as_posix(),
        "expected_sha256": expected_sha256,
        "observed_target_sha256": observed_sha256,
        "recovered_target_sha256": recovered_sha256,
        "artifact_size_bytes": artifact_size_bytes,
        "quarantine_path": quarantine_path.as_posix() if quarantine_path else None,
        "status": status,
        "reason": reason,
        "source_verified_before_mutation": status != "REJECTED_SOURCE_MISMATCH",
        "corrupted_bytes_preserved": quarantine_path is not None,
        "atomic_replace_attempted": mutation_applied,
        "mutation_applied": mutation_applied,
        "live_process_memory_modified": False,
        "automatic_execution": False,
        "write_authority": "EXPLICIT_TARGET_RECOVERY_ONLY",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Recovery establishes byte equality with an independently supplied "
            "expected SHA-256 only. It does not prove source trust, semantic "
            "correctness, process quiescence, or permission to execute the artifact."
        ),
    }


def recover_verified_artifact(
    target: str | Path,
    trusted_source: str | Path,
    *,
    expected_sha256: str,
    quarantine_directory: str | Path,
) -> dict[str, Any]:
    """Restore one artifact from independently verified bytes.

    The caller must stop processes using the target before invoking recovery.
    Replacement is atomic at the filesystem rename boundary when the platform
    and target filesystem support ``os.replace``.
    """
    if type(expected_sha256) is not str or SHA256.fullmatch(expected_sha256) is None:
        raise VerifiedArtifactRecoveryError(
            "expected_sha256 must be 64 lowercase hexadecimal characters"
        )
    target_path = Path(target).absolute()
    source_path = Path(trusted_source).absolute()
    quarantine = Path(quarantine_directory).absolute()
    if target_path == source_path:
        raise VerifiedArtifactRecoveryError("target and trusted_source must differ")
    _regular_file(source_path, "trusted_source")
    _regular_file(target_path, "target", may_be_missing=True)
    if quarantine.is_symlink():
        raise VerifiedArtifactRecoveryError(
            "quarantine_directory must not be a symbolic link"
        )
    quarantine.mkdir(parents=True, exist_ok=True)
    if not quarantine.is_dir():
        raise VerifiedArtifactRecoveryError("quarantine_directory must be a directory")

    source_hash, source_size = _digest(source_path)
    observed_hash: str | None = None
    if target_path.exists():
        observed_hash, _ = _digest(target_path)

    if source_hash != expected_sha256:
        return _receipt(_body(
            target=target_path, trusted_source=source_path,
            expected_sha256=expected_sha256, observed_sha256=observed_hash,
            recovered_sha256=observed_hash, artifact_size_bytes=source_size,
            quarantine_path=None, status="REJECTED_SOURCE_MISMATCH",
            reason="TRUSTED_SOURCE_HASH_MISMATCH", mutation_applied=False,
        ))
    if observed_hash == expected_sha256:
        return _receipt(_body(
            target=target_path, trusted_source=source_path,
            expected_sha256=expected_sha256, observed_sha256=observed_hash,
            recovered_sha256=observed_hash, artifact_size_bytes=source_size,
            quarantine_path=None, status="NO_ACTION",
            reason="TARGET_ALREADY_MATCHES", mutation_applied=False,
        ))

    quarantine_path: Path | None = None
    if target_path.exists():
        quarantine_path = quarantine / f"{target_path.name}.{observed_hash}.corrupt"
        if quarantine_path.exists():
            _regular_file(quarantine_path, "quarantine artifact")
            quarantine_hash, _ = _digest(quarantine_path)
            if quarantine_hash != observed_hash:
                raise VerifiedArtifactRecoveryError(
                    "existing quarantine artifact does not match observed target"
                )
        else:
            try:
                with target_path.open("rb") as source, quarantine_path.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
            except OSError as exc:
                raise VerifiedArtifactRecoveryError(
                    "unable to preserve corrupted artifact"
                ) from exc
            quarantine_hash, _ = _digest(quarantine_path)
            if quarantine_hash != observed_hash:
                raise VerifiedArtifactRecoveryError(
                    "quarantined bytes do not match observed target"
                )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=target_path.parent, prefix=f".{target_path.name}.",
            suffix=".recovery", delete=False,
        ) as output, source_path.open("rb") as source:
            temporary_path = Path(output.name)
            shutil.copyfileobj(source, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        staged_hash, _ = _digest(temporary_path)
        if staged_hash != expected_sha256:
            raise VerifiedArtifactRecoveryError(
                "staged recovery artifact hash mismatch"
            )
        source_mode = stat.S_IMODE(source_path.stat().st_mode)
        os.chmod(temporary_path, source_mode)
        os.replace(temporary_path, target_path)
        temporary_path = None
    except OSError as exc:
        raise VerifiedArtifactRecoveryError(
            "atomic target replacement failed; ensure the target process is stopped"
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    recovered_hash, recovered_size = _digest(target_path)
    if recovered_hash != expected_sha256:
        raise VerifiedArtifactRecoveryError("post-recovery target hash mismatch")
    return _receipt(_body(
        target=target_path, trusted_source=source_path,
        expected_sha256=expected_sha256, observed_sha256=observed_hash,
        recovered_sha256=recovered_hash, artifact_size_bytes=recovered_size,
        quarantine_path=quarantine_path, status="RECOVERED",
        reason="VERIFIED_ATOMIC_REPLACEMENT", mutation_applied=True,
    ))


def validate_verified_artifact_recovery_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Fail closed when a stored recovery receipt is altered or contradictory."""
    if type(receipt) is not dict:
        raise VerifiedArtifactRecoveryError("receipt must be a plain dictionary")
    expected = {
        "type", "version", "target_path", "trusted_source_path",
        "expected_sha256", "observed_target_sha256", "recovered_target_sha256",
        "artifact_size_bytes", "quarantine_path", "status", "reason",
        "source_verified_before_mutation", "corrupted_bytes_preserved",
        "atomic_replace_attempted", "mutation_applied",
        "live_process_memory_modified", "automatic_execution", "write_authority",
        "execution_authority", "interpretation_notice", "receipt_hash",
    }
    if set(receipt) != expected:
        raise VerifiedArtifactRecoveryError(
            "receipt fields do not match the versioned schema"
        )
    if receipt["type"] != RECOVERY_TYPE or receipt["version"] != RECOVERY_VERSION:
        raise VerifiedArtifactRecoveryError("receipt type or version is invalid")
    status = receipt["status"]
    if status not in {"RECOVERED", "NO_ACTION", "REJECTED_SOURCE_MISMATCH"}:
        raise VerifiedArtifactRecoveryError("receipt status is invalid")
    mutated = status == "RECOVERED"
    if receipt["mutation_applied"] is not mutated:
        raise VerifiedArtifactRecoveryError("mutation claim contradicts status")
    if receipt["atomic_replace_attempted"] is not mutated:
        raise VerifiedArtifactRecoveryError("atomic replacement claim contradicts status")
    if receipt["live_process_memory_modified"] is not False:
        raise VerifiedArtifactRecoveryError("receipt cannot claim live-memory mutation")
    if receipt["automatic_execution"] is not False or receipt["execution_authority"] != "NONE":
        raise VerifiedArtifactRecoveryError("receipt cannot grant execution")
    expected_hash = receipt["expected_sha256"]
    if type(expected_hash) is not str or SHA256.fullmatch(expected_hash) is None:
        raise VerifiedArtifactRecoveryError("receipt expected hash is invalid")
    if status in {"RECOVERED", "NO_ACTION"} and receipt["recovered_target_sha256"] != expected_hash:
        raise VerifiedArtifactRecoveryError("successful receipt target hash mismatch")
    body = dict(receipt)
    supplied = body.pop("receipt_hash")
    if supplied != stable_hash(body):
        raise VerifiedArtifactRecoveryError("receipt hash mismatch")
    return True
