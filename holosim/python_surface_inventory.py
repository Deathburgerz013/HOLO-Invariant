"""Deterministic, non-executing inventory of declared Python source files."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


RECEIPT_TYPE = "python_surface_inventory_receipt"
RECEIPT_VERSION = 1
DEFAULT_SURFACE_ROOTS = ("examples", "holosim", "tests")

_RECEIPT_FIELDS = {
    "type",
    "version",
    "python_paths",
    "files",
    "file_count",
    "inventory_hash",
    "observation_only",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "receipt_hash",
}


class PythonSurfaceInventoryError(ValueError):
    """Raised when a Python surface cannot be inventoried honestly."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise PythonSurfaceInventoryError("inventory could not be canonicalized") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _source_hash(source: str) -> str:
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise PythonSurfaceInventoryError("python path must be a non-empty string")
    if "\\" in value:
        raise PythonSurfaceInventoryError("python paths must use portable separators")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        raise PythonSurfaceInventoryError(f"invalid Python path: {value}")
    normalized = path.as_posix()
    if normalized in {".", ""}:
        raise PythonSurfaceInventoryError("python path is empty")
    return normalized


def _surface_kind(path: PurePosixPath) -> str:
    if path.parts[0] == "examples":
        return "EXAMPLE"
    if path.parts[0] == "tests" or "tests" in path.parts[:-1] or path.name.startswith("test_"):
        return "TEST"
    if path.parts[0] == "holosim":
        return "IMPLEMENTATION"
    return "OTHER"


def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    return (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _analyze_source(source: str, path: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise PythonSurfaceInventoryError(f"invalid Python syntax: {path}") from exc

    functions: set[str] = set()
    classes: set[str] = set()
    constants: dict[str, Any] = {}
    imports: set[str] = set()
    executable = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.add(node.name)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add("." * node.level + node.module)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
        ):
            constants[node.targets[0].id] = node.value.value
        executable = executable or _is_main_guard(node)

    contracts = []
    for name, value in sorted(constants.items()):
        if not (name == "RECEIPT_TYPE" or name.endswith("_RECEIPT_TYPE")):
            continue
        version_name = name.removesuffix("TYPE") + "VERSION"
        version = constants.get(version_name)
        if (
            isinstance(value, str)
            and value
            and isinstance(version, int)
            and not isinstance(version, bool)
            and version > 0
        ):
            contracts.append({
                "type_constant": name,
                "type": value,
                "version_constant": version_name,
                "version": version,
            })

    pure_path = PurePosixPath(path)
    return {
        "path": path,
        "source_sha256": _source_hash(source),
        "surface_kind": _surface_kind(pure_path),
        "top_level_functions": sorted(functions),
        "top_level_classes": sorted(classes),
        "imported_modules": sorted(imports),
        "declared_receipt_contracts": contracts,
        "has_main_guard": executable,
        "is_package_initializer": pure_path.name == "__init__.py",
    }


def discover_python_paths(
    *, root: str | Path, surface_roots: Sequence[str] = DEFAULT_SURFACE_ROOTS
) -> list[str]:
    """Discover every Python file inside explicit repository surface roots."""
    if isinstance(surface_roots, (str, bytes)) or not isinstance(surface_roots, Sequence):
        raise PythonSurfaceInventoryError("surface_roots must be a sequence")
    names = []
    for value in surface_roots:
        if not isinstance(value, str) or not value or "/" in value or "\\" in value:
            raise PythonSurfaceInventoryError("surface root must be one path segment")
        names.append(value)
    if not names or len(names) != len(set(names)):
        raise PythonSurfaceInventoryError("surface roots must be non-empty and unique")

    root_path = Path(root).resolve()
    paths: list[str] = []
    for name in sorted(names):
        surface = root_path / name
        if not surface.is_dir() or surface.is_symlink():
            raise PythonSurfaceInventoryError(f"surface root is unavailable: {name}")
        for candidate in surface.rglob("*.py"):
            resolved = candidate.resolve()
            if root_path not in resolved.parents or candidate.is_symlink():
                raise PythonSurfaceInventoryError(
                    f"Python discovery crossed a link boundary: {candidate}"
                )
            paths.append(candidate.relative_to(root_path).as_posix())
    return sorted(paths)


def build_python_surface_inventory(
    *, root: str | Path, python_paths: Sequence[str]
) -> dict[str, Any]:
    """Inventory caller-declared Python paths without importing or executing them."""
    if isinstance(python_paths, (str, bytes)) or not isinstance(python_paths, Sequence):
        raise PythonSurfaceInventoryError("python_paths must be a sequence")
    normalized = [_normalize_path(value) for value in python_paths]
    if not normalized:
        raise PythonSurfaceInventoryError("python_paths must not be empty")
    if len(normalized) != len(set(normalized)):
        raise PythonSurfaceInventoryError("duplicate Python path")
    normalized.sort()

    root_path = Path(root).resolve()
    files = []
    for relative in normalized:
        candidate = (root_path / relative).resolve()
        if root_path not in candidate.parents:
            raise PythonSurfaceInventoryError(f"Python path escapes root: {relative}")
        try:
            source = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PythonSurfaceInventoryError(f"Python source unreadable: {relative}") from exc
        files.append(_analyze_source(source, relative))

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "python_paths": normalized,
        "files": files,
        "file_count": len(files),
        "inventory_hash": _hash(files),
        "observation_only": True,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt records syntax-visible facts for caller-declared Python "
            "paths. It does not prove completeness, runtime behavior, usefulness, "
            "agent identity, validity, acceptance, or authority."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_python_surface_inventory(
    receipt: Mapping[str, Any], *, root: str | Path
) -> dict[str, Any]:
    """Rebuild an inventory and report mismatch without granting authority."""
    failures: list[str] = []
    if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_FIELDS:
        raise PythonSurfaceInventoryError("receipt fields mismatch")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        failures.append("receipt_contract_mismatch")
    if receipt["observation_only"] is not True:
        failures.append("observation_boundary_mismatch")
    if receipt["accepted"] is not False or receipt["write_authority"] != "NONE":
        failures.append("forbidden_authority")

    try:
        rebuilt = build_python_surface_inventory(
            root=root, python_paths=receipt["python_paths"]
        )
    except PythonSurfaceInventoryError:
        rebuilt = None
        failures.append("inventory_rebuild_failed")
    if rebuilt is not None:
        for field in (
            "python_paths",
            "files",
            "file_count",
            "inventory_hash",
            "interpretation_notice",
        ):
            if receipt[field] != rebuilt[field]:
                failures.append(f"{field}_mismatch")

    body = {key: receipt[key] for key in receipt if key != "receipt_hash"}
    if receipt["receipt_hash"] != _hash(body):
        failures.append("receipt_hash_mismatch")

    result_body = {
        "type": "python_surface_inventory_check",
        "version": 1,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "inventory_hash": receipt["inventory_hash"],
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**result_body, "check_hash": _hash(result_body)}
