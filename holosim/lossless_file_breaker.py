"""Lossless derived workspaces for files too large to handle monolithically."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, BinaryIO


MANIFEST_TYPE = "holo_lossless_file_break"
MANIFEST_VERSION = 1
MANIFEST_NAME = "manifest.json"


class LosslessFileBreakerError(ValueError):
    """Raised when a file break or reconstruction is unsafe or invalid."""


def _canonical_json(value: Any, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise LosslessFileBreakerError(
            f"{label} must contain only JSON values"
        ) from exc


def _canonical_hash(value: Any, *, label: str) -> str:
    return hashlib.sha256(
        _canonical_json(value, label=label).encode("utf-8")
    ).hexdigest()


def _sha256_file(handle: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        block = handle.read(1024 * 1024)
        if not block:
            break
        digest.update(block)
        size += len(block)
    return digest.hexdigest(), size


def _load_manifest(workspace: Path) -> dict[str, Any]:
    manifest_path = workspace / MANIFEST_NAME
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LosslessFileBreakerError("manifest file is missing") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LosslessFileBreakerError(f"manifest could not be loaded: {exc}") from exc
    if not isinstance(value, dict):
        raise LosslessFileBreakerError("manifest must contain a JSON object")
    return value


def _validate_digest(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise LosslessFileBreakerError(f"{label} must be a SHA-256 hex digest")
    return value


def create_lossless_file_break(
    source_path: str | Path,
    workspace_path: str | Path,
    *,
    max_chunk_bytes: int,
) -> dict[str, Any]:
    """Copy a source into bounded hash-linked chunks without modifying it."""
    if (
        type(max_chunk_bytes) is not int
        or isinstance(max_chunk_bytes, bool)
        or max_chunk_bytes <= 0
    ):
        raise LosslessFileBreakerError(
            "max_chunk_bytes must be a positive integer"
        )

    source = Path(source_path)
    workspace = Path(workspace_path)
    if workspace.exists():
        raise LosslessFileBreakerError("workspace path already exists")
    if not source.is_file():
        raise LosslessFileBreakerError("source path must be an existing file")
    if not workspace.parent.exists() or not workspace.parent.is_dir():
        raise LosslessFileBreakerError("workspace parent must be an existing directory")

    workspace.mkdir()
    chunks: list[dict[str, Any]] = []
    source_digest = hashlib.sha256()
    source_size = 0
    index = 0

    try:
        with source.open("rb") as source_handle:
            while True:
                content = source_handle.read(max_chunk_bytes)
                if not content:
                    break
                filename = f"chunk-{index:08d}.bin"
                (workspace / filename).write_bytes(content)
                chunks.append(
                    {
                        "index": index,
                        "filename": filename,
                        "offset": source_size,
                        "length": len(content),
                        "hash": hashlib.sha256(content).hexdigest(),
                    }
                )
                source_digest.update(content)
                source_size += len(content)
                index += 1

        body: dict[str, Any] = {
            "type": MANIFEST_TYPE,
            "version": MANIFEST_VERSION,
            "source_name": source.name,
            "source_size": source_size,
            "source_hash": source_digest.hexdigest(),
            "max_chunk_bytes": max_chunk_bytes,
            "chunks": chunks,
            "source_mutation": False,
            "source_write_authority": "NONE",
            "derived_workspace_write": True,
            "canonical_mutation": False,
            "accepted": False,
            "truth_claimed": False,
        }
        manifest = {
            **body,
            "manifest_hash": _canonical_hash(body, label="manifest"),
        }
        (workspace / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        # Remove only files created inside the new, previously absent workspace.
        for created in workspace.iterdir():
            if created.is_file() and not created.is_symlink():
                created.unlink()
        workspace.rmdir()
        raise

    return manifest


def verify_lossless_file_break(
    workspace_path: str | Path,
) -> dict[str, Any]:
    """Verify manifest integrity, chunk boundaries, and exact source identity."""
    workspace = Path(workspace_path)
    if not workspace.is_dir():
        raise LosslessFileBreakerError("workspace path must be a directory")

    manifest = _load_manifest(workspace)
    required_fields = {
        "type",
        "version",
        "source_name",
        "source_size",
        "source_hash",
        "max_chunk_bytes",
        "chunks",
        "source_mutation",
        "source_write_authority",
        "derived_workspace_write",
        "canonical_mutation",
        "accepted",
        "truth_claimed",
        "manifest_hash",
    }
    if set(manifest) != required_fields:
        raise LosslessFileBreakerError("manifest fields are invalid")

    supplied_hash = manifest["manifest_hash"]
    _validate_digest(supplied_hash, label="manifest_hash")
    body = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    if _canonical_hash(body, label="manifest") != supplied_hash:
        raise LosslessFileBreakerError("manifest hash mismatch")

    if manifest["type"] != MANIFEST_TYPE:
        raise LosslessFileBreakerError("manifest type mismatch")
    if manifest["version"] != MANIFEST_VERSION:
        raise LosslessFileBreakerError("manifest version mismatch")
    if type(manifest["source_size"]) is not int or manifest["source_size"] < 0:
        raise LosslessFileBreakerError("source_size must be a non-negative integer")
    if type(manifest["max_chunk_bytes"]) is not int or manifest["max_chunk_bytes"] <= 0:
        raise LosslessFileBreakerError("max_chunk_bytes must be a positive integer")
    _validate_digest(manifest["source_hash"], label="source_hash")
    if not isinstance(manifest["chunks"], list):
        raise LosslessFileBreakerError("chunks must be a list")

    bounded = {
        "source_mutation": False,
        "source_write_authority": "NONE",
        "derived_workspace_write": True,
        "canonical_mutation": False,
        "accepted": False,
        "truth_claimed": False,
    }
    for field, expected in bounded.items():
        if manifest[field] != expected:
            raise LosslessFileBreakerError(f"invalid bounded field {field}")

    root = workspace.resolve()
    expected_offset = 0
    reconstructed_digest = hashlib.sha256()

    for expected_index, chunk in enumerate(manifest["chunks"]):
        if not isinstance(chunk, Mapping) or set(chunk) != {
            "index", "filename", "offset", "length", "hash"
        }:
            raise LosslessFileBreakerError("chunk fields are invalid")
        if chunk["index"] != expected_index:
            raise LosslessFileBreakerError("chunk index is not contiguous")
        if chunk["offset"] != expected_offset:
            raise LosslessFileBreakerError("chunk offset is not contiguous")
        filename = chunk["filename"]
        if not isinstance(filename, str) or not filename:
            raise LosslessFileBreakerError("chunk filename is invalid")
        chunk_path = workspace / filename
        resolved = chunk_path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise LosslessFileBreakerError("chunk path escapes workspace") from exc
        if chunk_path.is_symlink():
            raise LosslessFileBreakerError("chunk path must not be a symbolic link")
        if not chunk_path.is_file():
            raise LosslessFileBreakerError("chunk file is missing")
        content = chunk_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != chunk["hash"]:
            raise LosslessFileBreakerError("chunk hash mismatch")
        if chunk["length"] != len(content):
            raise LosslessFileBreakerError("chunk length mismatch")
        if len(content) > manifest["max_chunk_bytes"]:
            raise LosslessFileBreakerError("chunk exceeds maximum size")
        reconstructed_digest.update(content)
        expected_offset += len(content)

    if expected_offset != manifest["source_size"]:
        raise LosslessFileBreakerError("source size does not match chunks")
    if reconstructed_digest.hexdigest() != manifest["source_hash"]:
        raise LosslessFileBreakerError("reconstructed source hash mismatch")
    return manifest


def reconstruct_lossless_file(
    workspace_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Reconstruct verified chunks into a new candidate file only."""
    workspace = Path(workspace_path)
    output = Path(output_path)
    if output.exists():
        raise LosslessFileBreakerError("output path already exists")
    if not output.parent.exists() or not output.parent.is_dir():
        raise LosslessFileBreakerError("output parent must be an existing directory")

    manifest = verify_lossless_file_break(workspace)
    digest = hashlib.sha256()
    size = 0
    try:
        with output.open("xb") as output_handle:
            for chunk in manifest["chunks"]:
                content = (workspace / chunk["filename"]).read_bytes()
                output_handle.write(content)
                digest.update(content)
                size += len(content)
    except Exception:
        if output.exists() and output.is_file():
            output.unlink()
        raise

    output_hash = digest.hexdigest()
    exact = size == manifest["source_size"] and output_hash == manifest["source_hash"]
    if not exact:
        output.unlink()
        raise LosslessFileBreakerError("reconstructed output does not match source")

    return {
        "type": "holo_lossless_file_reconstruction",
        "version": 1,
        "manifest_hash": manifest["manifest_hash"],
        "output_name": output.name,
        "output_size": size,
        "output_hash": output_hash,
        "exact_round_trip": True,
        "source_mutation": False,
        "canonical_mutation": False,
        "accepted": False,
        "truth_claimed": False,
    }
