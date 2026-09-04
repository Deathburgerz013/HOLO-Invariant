"""Version-bound registry for explicit software guarantees."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


GUARANTEE_REGISTRY_TYPE = "holo_guarantee_registry"
GUARANTEE_REGISTRY_VERSION = 1
BOUNDARY_REGISTER_TYPE = "holo_verified_boundary_register"
BOUNDARY_REGISTER_VERSION = 1

_BOUNDARY_FIELDS = {
    "boundary_id",
    "module",
    "implementation_path",
    "implementation_sha256",
    "receipts",
    "test_path",
    "test_sha256",
}

_RECEIPT_CONTRACT_FIELDS = {
    "type_constant",
    "type",
    "version_constant",
    "version",
    "verifier",
}

_BOUNDARY_REGISTER_FIELDS = {
    "type",
    "version",
    "boundaries",
    "accepted",
    "write_authority",
    "register_hash",
}


class GuaranteeRegistryError(ValueError):
    """Raised when a guarantee registry cannot be built honestly."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise GuaranteeRegistryError(
            "guarantee registry could not be canonicalized"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuaranteeRegistryError(f"{field} must be a non-empty string")
    return value


def _validate_string_list(value: Any, field: str) -> list[str]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not value
    ):
        raise GuaranteeRegistryError(
            f"{field} must be a non-empty sequence"
        )

    result: list[str] = []
    for index, item in enumerate(value):
        result.append(
            _require_nonempty_string(item, f"{field}[{index}]")
        )

    return result


def _validate_guarantee(
    guarantee: Mapping[str, Any],
) -> dict[str, Any]:
    required_fields = {
        "guarantee_id",
        "guarantee_type",
        "scope",
        "dependencies",
        "validator",
        "failure_condition",
        "evidence",
    }

    if set(guarantee) != required_fields:
        raise GuaranteeRegistryError("guarantee fields are invalid")

    return {
        "guarantee_id": _require_nonempty_string(
            guarantee["guarantee_id"],
            "guarantee_id",
        ),
        "guarantee_type": _require_nonempty_string(
            guarantee["guarantee_type"],
            "guarantee_type",
        ),
        "scope": _require_nonempty_string(
            guarantee["scope"],
            "scope",
        ),
        "dependencies": _validate_string_list(
            guarantee["dependencies"],
            "dependencies",
        ),
        "validator": _require_nonempty_string(
            guarantee["validator"],
            "validator",
        ),
        "failure_condition": _require_nonempty_string(
            guarantee["failure_condition"],
            "failure_condition",
        ),
        "evidence": _validate_string_list(
            guarantee["evidence"],
            "evidence",
        ),
    }


def build_guarantee_registry(
    guarantees: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic, read-only registry of bounded guarantees."""
    if (
        isinstance(guarantees, (str, bytes))
        or not isinstance(guarantees, Sequence)
        or not guarantees
    ):
        raise GuaranteeRegistryError(
            "guarantees must be a non-empty sequence"
        )

    validated_guarantees: list[dict[str, Any]] = []
    guarantee_ids: set[str] = set()

    for index, guarantee in enumerate(guarantees):
        if not isinstance(guarantee, Mapping):
            raise GuaranteeRegistryError(
                f"guarantee at index {index} must be a mapping"
            )

        validated = _validate_guarantee(guarantee)
        guarantee_id = validated["guarantee_id"]

        if guarantee_id in guarantee_ids:
            raise GuaranteeRegistryError("duplicate guarantee_id")

        guarantee_ids.add(guarantee_id)
        validated_guarantees.append(validated)

    body = {
        "type": GUARANTEE_REGISTRY_TYPE,
        "version": GUARANTEE_REGISTRY_VERSION,
        "guarantees": validated_guarantees,
        "accepted": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "registry_hash": _canonical_hash(body),
    }


def _require_sha256(value: Any, field: str) -> str:
    value = _require_nonempty_string(value, field)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise GuaranteeRegistryError(f"{field} must be lowercase SHA-256")
    return value


def _validate_boundary(boundary: Mapping[str, Any]) -> dict[str, Any]:
    if set(boundary) != _BOUNDARY_FIELDS:
        raise GuaranteeRegistryError("boundary fields are invalid")

    receipts_value = boundary["receipts"]
    if (
        isinstance(receipts_value, (str, bytes))
        or not isinstance(receipts_value, Sequence)
        or not receipts_value
    ):
        raise GuaranteeRegistryError("receipts must be a non-empty sequence")
    receipts: list[dict[str, Any]] = []
    verifiers: set[str] = set()
    for receipt in receipts_value:
        if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_CONTRACT_FIELDS:
            raise GuaranteeRegistryError("receipt contract fields are invalid")
        version = receipt["version"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise GuaranteeRegistryError("receipt version must be a positive integer")
        verifier = _require_nonempty_string(receipt["verifier"], "verifier")
        if verifier in verifiers:
            raise GuaranteeRegistryError("duplicate receipt verifier")
        verifiers.add(verifier)
        receipts.append({
            "type_constant": _require_nonempty_string(
                receipt["type_constant"], "type_constant"
            ),
            "type": _require_nonempty_string(receipt["type"], "receipt type"),
            "version_constant": _require_nonempty_string(
                receipt["version_constant"], "version_constant"
            ),
            "version": version,
            "verifier": verifier,
        })

    return {
        "boundary_id": _require_nonempty_string(
            boundary["boundary_id"], "boundary_id"
        ),
        "module": _require_nonempty_string(boundary["module"], "module"),
        "implementation_path": _require_nonempty_string(
            boundary["implementation_path"], "implementation_path"
        ),
        "implementation_sha256": _require_sha256(
            boundary["implementation_sha256"], "implementation_sha256"
        ),
        "receipts": receipts,
        "test_path": _require_nonempty_string(boundary["test_path"], "test_path"),
        "test_sha256": _require_sha256(boundary["test_sha256"], "test_sha256"),
    }


def validate_boundary_register(register: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one closed, read-only boundary register."""
    if not isinstance(register, Mapping) or set(register) != _BOUNDARY_REGISTER_FIELDS:
        raise GuaranteeRegistryError("boundary register fields are invalid")
    if register["type"] != BOUNDARY_REGISTER_TYPE:
        raise GuaranteeRegistryError("boundary register type is invalid")
    if register["version"] != BOUNDARY_REGISTER_VERSION:
        raise GuaranteeRegistryError("boundary register version is invalid")
    if register["accepted"] is not False or register["write_authority"] != "NONE":
        raise GuaranteeRegistryError("boundary register grants forbidden authority")
    if (
        isinstance(register["boundaries"], (str, bytes))
        or not isinstance(register["boundaries"], Sequence)
        or not register["boundaries"]
    ):
        raise GuaranteeRegistryError("boundaries must be a non-empty sequence")

    boundaries = []
    boundary_ids: set[str] = set()
    for item in register["boundaries"]:
        if not isinstance(item, Mapping):
            raise GuaranteeRegistryError("boundary must be a mapping")
        boundary = _validate_boundary(item)
        if boundary["boundary_id"] in boundary_ids:
            raise GuaranteeRegistryError("duplicate boundary_id")
        boundary_ids.add(boundary["boundary_id"])
        boundaries.append(boundary)

    if [item["boundary_id"] for item in boundaries] != sorted(boundary_ids):
        raise GuaranteeRegistryError("boundaries must be sorted by boundary_id")

    supplied_hash = _require_sha256(register["register_hash"], "register_hash")
    body = {
        "type": BOUNDARY_REGISTER_TYPE,
        "version": BOUNDARY_REGISTER_VERSION,
        "boundaries": boundaries,
        "accepted": False,
        "write_authority": "NONE",
    }
    if _canonical_hash(body) != supplied_hash:
        raise GuaranteeRegistryError("boundary register hash mismatch")
    return {**body, "register_hash": supplied_hash}


def load_boundary_register(path: str | Path) -> dict[str, Any]:
    """Load a committed boundary register without importing registered code."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GuaranteeRegistryError("boundary register could not be loaded") from exc
    if not isinstance(value, Mapping):
        raise GuaranteeRegistryError("boundary register must contain an object")
    return validate_boundary_register(value)


def lookup_boundary(
    register: Mapping[str, Any], boundary_id: str
) -> dict[str, Any]:
    """Return one verified keyed slot or fail closed when it is absent."""
    checked = validate_boundary_register(register)
    boundary_id = _require_nonempty_string(boundary_id, "boundary_id")
    for boundary in checked["boundaries"]:
        if boundary["boundary_id"] == boundary_id:
            return dict(boundary)
    raise GuaranteeRegistryError(f"boundary_id is not registered: {boundary_id}")


def _source_symbols(source: str, path: str) -> tuple[dict[str, Any], set[str]]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise GuaranteeRegistryError(f"registered implementation is invalid Python: {path}") from exc
    constants: dict[str, Any] = {}
    functions: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
        ):
            constants[node.targets[0].id] = node.value.value
    return constants, functions


def _portable_text_hash(content: bytes, path: str) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeError as exc:
        raise GuaranteeRegistryError(
            f"registered text artifact is not UTF-8: {path}"
        ) from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_boundary_register(
    register: Mapping[str, Any], *, root: str | Path
) -> dict[str, Any]:
    """Check registered files, hashes, receipt constants, and verifier symbols."""
    checked = validate_boundary_register(register)
    root_path = Path(root).resolve()
    results: list[dict[str, Any]] = []

    for boundary in checked["boundaries"]:
        failures: list[str] = []
        implementation = (root_path / boundary["implementation_path"]).resolve()
        test = (root_path / boundary["test_path"]).resolve()
        for candidate, label in ((implementation, "implementation"), (test, "test")):
            if root_path not in candidate.parents:
                failures.append(f"{label}_path_outside_root")
                continue
            try:
                content = candidate.read_bytes()
            except OSError:
                failures.append(f"{label}_missing")
                continue
            expected = boundary[f"{label}_sha256"]
            if _portable_text_hash(content, str(candidate)) != expected:
                failures.append(f"{label}_hash_mismatch")

        if not any(item.startswith("implementation_") for item in failures):
            source = implementation.read_text(encoding="utf-8")
            constants, functions = _source_symbols(
                source, boundary["implementation_path"]
            )
            for receipt in boundary["receipts"]:
                if constants.get(receipt["type_constant"]) != receipt["type"]:
                    failures.append(f"receipt_type_mismatch:{receipt['verifier']}")
                if constants.get(receipt["version_constant"]) != receipt["version"]:
                    failures.append(f"receipt_version_mismatch:{receipt['verifier']}")
                if receipt["verifier"] not in functions:
                    failures.append(f"verifier_missing:{receipt['verifier']}")

        results.append({
            "boundary_id": boundary["boundary_id"],
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
        })

    body = {
        "type": "holo_verified_boundary_register_check",
        "version": 1,
        "register_hash": checked["register_hash"],
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
        "results": results,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "check_hash": _canonical_hash(body)}
