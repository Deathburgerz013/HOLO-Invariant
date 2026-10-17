"""Read-only, declared-failure information insurance experiment."""

import hashlib
import json
from pathlib import Path

MAX_COPIES = 256
MAX_RAW_BYTES = 65_536
MAX_MANIFEST_BYTES = 65_536
MAX_CHUNK_BYTES = 65_536
MAX_WORKSPACE_BYTES = 1_048_576
MAX_WORKSPACE_CHUNKS = 256
MAX_WORKSPACES = 8

from holosim.lossless_file_breaker import (
    LosslessFileBreakerError,
    MANIFEST_TYPE,
    MANIFEST_VERSION,
    _canonical_hash,
)



def _verify_bounded_workspace(workspace_path):
    """Verify one stable workspace with bounded reads and no writes."""
    workspace = Path(workspace_path)
    if not workspace.is_dir():
        raise ValueError("workspace is not a directory")

    manifest_path = workspace / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("manifest symlink")

    with manifest_path.open("rb") as handle:
        raw = handle.read(MAX_MANIFEST_BYTES + 1)

    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds limit")

    manifest = json.loads(raw)
    required = {
        "type", "version", "source_name", "source_size",
        "source_hash", "max_chunk_bytes", "chunks",
        "source_mutation", "source_write_authority",
        "derived_workspace_write", "canonical_mutation",
        "accepted", "truth_claimed", "manifest_hash",
    }
    if type(manifest) is not dict or set(manifest) != required:
        raise ValueError("manifest schema mismatch")

    def digest_valid(value):
        return (
            type(value) is str
            and len(value) == 64
            and all(c in "0123456789abcdef" for c in value)
        )

    if not digest_valid(manifest["manifest_hash"]):
        raise ValueError("invalid manifest hash")

    body = dict(manifest)
    supplied_hash = body.pop("manifest_hash")
    if _canonical_hash(body, label="manifest") != supplied_hash:
        raise ValueError("manifest hash mismatch")

    if (
        manifest["type"] != MANIFEST_TYPE
        or type(manifest["version"]) is not int
        or manifest["version"] != MANIFEST_VERSION
        or type(manifest["source_size"]) is not int
        or not 0 <= manifest["source_size"] <= MAX_WORKSPACE_BYTES
        or type(manifest["max_chunk_bytes"]) is not int
        or not 0 < manifest["max_chunk_bytes"] <= MAX_CHUNK_BYTES
        or not digest_valid(manifest["source_hash"])
        or type(manifest["chunks"]) is not list
        or len(manifest["chunks"]) > MAX_WORKSPACE_CHUNKS
    ):
        raise ValueError("invalid manifest limits or identity")

    flags = {
        "source_mutation": False,
        "source_write_authority": "NONE",
        "derived_workspace_write": True,
        "canonical_mutation": False,
        "accepted": False,
        "truth_claimed": False,
    }
    for field, expected in flags.items():
        if type(manifest[field]) is not type(expected):
            raise ValueError("invalid authority field type")
        if manifest[field] != expected:
            raise ValueError("invalid authority field")

    root = workspace.resolve()
    source_digest = hashlib.sha256()
    total = 0

    for index, chunk in enumerate(manifest["chunks"]):
        if type(chunk) is not dict or set(chunk) != {
            "index", "filename", "offset", "length", "hash"
        }:
            raise ValueError("invalid chunk schema")

        if (
            type(chunk["index"]) is not int
            or chunk["index"] != index
            or type(chunk["offset"]) is not int
            or chunk["offset"] != total
            or type(chunk["length"]) is not int
            or not 0 <= chunk["length"] <= manifest["max_chunk_bytes"]
            or not digest_valid(chunk["hash"])
            or type(chunk["filename"]) is not str
            or not chunk["filename"]
        ):
            raise ValueError("invalid chunk metadata")

        chunk_path = workspace / chunk["filename"]
        if chunk_path.is_symlink():
            raise ValueError("chunk symlink")

        try:
            chunk_path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("chunk escapes workspace") from exc

        if not chunk_path.is_file():
            raise ValueError("missing chunk")

        with chunk_path.open("rb") as handle:
            content = handle.read(MAX_CHUNK_BYTES + 1)

        if len(content) > MAX_CHUNK_BYTES:
            raise ValueError("chunk exceeds limit")
        if len(content) != chunk["length"]:
            raise ValueError("chunk length mismatch")
        if hashlib.sha256(content).hexdigest() != chunk["hash"]:
            raise ValueError("chunk hash mismatch")

        total += len(content)
        if total > MAX_WORKSPACE_BYTES:
            raise ValueError("workspace exceeds limit")

        source_digest.update(content)

    if total != manifest["source_size"]:
        raise ValueError("source size mismatch")
    if source_digest.hexdigest() != manifest["source_hash"]:
        raise ValueError("source hash mismatch")

    return manifest["source_hash"]

def assess_information_insurance(
    *,
    expected_sha256,
    copies,
    failed_domains,
):
    """Evaluate verified recovery sufficiency under declared failure assumptions.

    Failure-domain labels are supplied assumptions, not independently
    verified physical storage facts. This function performs no recovery,
    restoration, or writes and grants no authority.
    """
    unknown = {
        "status": "UNKNOWN",
        "reconstruction_sufficient": False,
        "verified_raw_copies": 0,
        "verified_workspaces": 0,
        "surviving_verified_copies": 0,
        "survival_independently_verified": False,
        "failure_model": "DECLARED_ONLY",
        "write_authority": "NONE",
    }

    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_sha256)
        or not isinstance(failed_domains, (list, tuple))
        or not all(
            isinstance(domain, str) and bool(domain.strip())
            for domain in failed_domains
        )
        or not isinstance(copies, (list, tuple))
        or len(copies) > MAX_COPIES
        or not all(isinstance(copy, dict) for copy in copies)
        or sum(
            copy.get("workspace_path") is not None
            for copy in copies
        ) > MAX_WORKSPACES
        or any(
            isinstance(copy.get("data"), bytes)
            and len(copy["data"]) > MAX_RAW_BYTES
            for copy in copies
        )
    ):
        return unknown

    failed = set(failed_domains)
    surviving = 0
    verified_workspaces = 0
    verified_raw_copies = 0

    for copy in copies:
        domain = copy.get("failure_domain")

        if not isinstance(domain, str) or not domain.strip():
            continue

        if domain in failed:
            continue

        data = copy.get("data")
        if isinstance(data, bytes):
            if hashlib.sha256(data).hexdigest() == expected_sha256:
                surviving += 1
                verified_raw_copies += 1
            continue

        workspace_path = copy.get("workspace_path")
        if workspace_path is None:
            continue

        try:
            source_hash = _verify_bounded_workspace(workspace_path)
        except (
            LosslessFileBreakerError,
            OSError,
            TypeError,
            ValueError,
            UnicodeError,
        ):
            continue

        if source_hash == expected_sha256:
            surviving += 1
            verified_workspaces += 1

    return {
        "status": "UNKNOWN",
        "reconstruction_sufficient": surviving > 0,
        "verified_raw_copies": verified_raw_copies,
        "verified_workspaces": verified_workspaces,
        "surviving_verified_copies": surviving,
        "survival_independently_verified": False,
        "failure_model": "DECLARED_ONLY",
        "write_authority": "NONE",
    }
