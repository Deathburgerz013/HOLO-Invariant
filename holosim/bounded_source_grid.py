"""Read-only, bounded source definition grid.

Static source observations are not runtime verification, functional
reproduction, or authority to modify anything.

On Windows, recorded volume and file identifiers detect observed path
substitution when replacement identifiers differ. Filesystems may reuse
identifiers, so matching identifiers do not prove uninterrupted object
identity. Observation is not an atomic filesystem snapshot.
"""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path

from holosim.source_grid_windows_io import (
    WindowsSourceReadError,
    read_bounded_windows_source,
)
from typing import Any


class SourceGridError(ValueError):
    """Invalid or unobservable bounded source grid."""


def observe_source_grid(
    root: Path,
    *,
    max_files: int = 1000,
    max_definitions: int = 10000,
    max_file_bytes: int = 1_000_000,
) -> dict[str, Any]:
    """Inventory source definitions without importing repository code."""
    if type(max_files) is not int or not 1 <= max_files <= 10000:
        raise SourceGridError("invalid max_files")
    if type(max_definitions) is not int or not 1 <= max_definitions <= 100000:
        raise SourceGridError("invalid max_definitions")
    if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= 10000000:
        raise SourceGridError("invalid max_file_bytes")

    root = Path(root)
    if not root.is_dir():
        raise SourceGridError("source root missing")

    paths = []
    directories = [root]
    expected_identities: dict[tuple[str, ...], tuple[int, int]] = {}

    if os.name == "nt":
        try:
            root_info = root.stat(follow_symlinks=False)
        except OSError as exc:
            raise SourceGridError("source root unreadable") from exc

        if (
            root_info.st_ino <= 0
            or root_info.st_file_attributes & 0x400
        ):
            raise SourceGridError("source root identity unavailable")

        expected_identities[()] = (root_info.st_dev & 0xFFFFFFFF, root_info.st_ino)

    visited_directories = 0
    visited_entries = 0
    max_directories = max_files * 10
    max_entries = max_files * 100

    while directories:
        directory = directories.pop()
        visited_directories += 1

        if visited_directories > max_directories:
            raise SourceGridError("directory budget exceeded")

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited_entries += 1
                    if visited_entries > max_entries:
                        raise SourceGridError("directory entry budget exceeded")

                    if entry.is_symlink():
                        raise SourceGridError("symlink entry unsupported")

                    if os.name == "nt":
                        if entry.is_junction():
                            raise SourceGridError("reparse point unsupported")
                        metadata = entry.stat(follow_symlinks=False)
                        if metadata.st_file_attributes & 0x400:
                            raise SourceGridError("reparse point unsupported")

                    if entry.is_dir(follow_symlinks=False):
                        if visited_directories + len(directories) >= max_directories:
                            raise SourceGridError("directory budget exceeded")

                        child = Path(entry.path)
                        if os.name == "nt":
                            info = child.stat(follow_symlinks=False)
                            if (
                                info.st_ino <= 0
                                or info.st_file_attributes & 0x400
                            ):
                                raise SourceGridError(
                                    "directory identity unavailable"
                                )
                            expected_identities[
                                child.relative_to(root).parts
                            ] = (info.st_dev & 0xFFFFFFFF, info.st_ino)

                        directories.append(child)
                    elif entry.name.endswith(".py") and entry.is_file(
                        follow_symlinks=False
                    ):
                        if len(paths) >= max_files:
                            raise SourceGridError("file budget exceeded")

                        child = Path(entry.path)
                        if os.name == "nt":
                            info = child.stat(follow_symlinks=False)
                            if (
                                info.st_ino <= 0
                                or info.st_file_attributes & 0x400
                            ):
                                raise SourceGridError(
                                    "source identity unavailable"
                                )
                            expected_identities[
                                child.relative_to(root).parts
                            ] = (info.st_dev & 0xFFFFFFFF, info.st_ino)

                        paths.append(child)
        except OSError as exc:
            raise SourceGridError("source directory unreadable") from exc

    paths.sort()

    records: list[dict[str, Any]] = []
    file_hashes: dict[str, str] = {}
    seen_identities: set[tuple[str, str]] = set()

    for path in paths:
        try:
            if os.name == "nt":
                data = read_bounded_windows_source(
                    root,
                    path.relative_to(root),
                    max_file_bytes,
                    expected_identities=expected_identities,
                )
            else:
                if path.is_symlink():
                    raise SourceGridError("symlink source unsupported")
                with path.open("rb") as stream:
                    data = stream.read(max_file_bytes + 1)
        except (OSError, WindowsSourceReadError) as exc:
            raise SourceGridError("source unreadable or unsafe") from exc

        if len(data) > max_file_bytes:
            raise SourceGridError("file byte budget exceeded")

        try:
            tree = ast.parse(data.decode("utf-8-sig"))
        except (SyntaxError, UnicodeError) as exc:
            raise SourceGridError("source cannot be parsed") from exc

        relative = path.relative_to(root).as_posix()
        file_hashes[relative] = hashlib.sha256(data).hexdigest()

        def visit(node: ast.AST, scope: tuple[str, ...] = ()) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if len(records) >= max_definitions:
                        raise SourceGridError("definition budget exceeded")

                    qualified_name = ".".join((*scope, child.name))
                    identity = (relative, qualified_name)
                    if identity in seen_identities:
                        raise SourceGridError("duplicate qualified identity")
                    seen_identities.add(identity)

                    records.append({
                        "path": relative,
                        "qualified_name": qualified_name,
                        "line": child.lineno,
                        "kind": (
                            "ASYNC_FUNCTION"
                            if isinstance(child, ast.AsyncFunctionDef)
                            else "FUNCTION"
                        ),
                        "definition_sha256": hashlib.sha256(
                            ast.dump(child, include_attributes=False).encode("utf-8")
                        ).hexdigest(),
                    })
                    visit(child, (*scope, child.name))
                elif isinstance(child, ast.ClassDef):
                    visit(child, (*scope, child.name))
                else:
                    visit(child, scope)

        try:
            visit(tree)
        except RecursionError as exc:
            raise SourceGridError(
                "definition nesting budget exceeded"
            ) from exc

    records.sort(
        key=lambda item: (
            item["path"],
            item["line"],
            item["qualified_name"],
        )
    )

    return {
        "type": "bounded_source_grid",
        "files_observed": len(paths),
        "file_hashes": file_hashes,
        "definitions": records,
        "runtime_verified": False,
        "functional_contracts_verified": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def compare_source_grids(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare complete bounded observations without accepting changes."""
    def index(grid: dict[str, Any]) -> dict[tuple[str, str], str]:
        if (
            type(grid) is not dict
            or set(grid) != {
                "type", "files_observed", "file_hashes", "definitions",
                "runtime_verified", "functional_contracts_verified",
                "accepted", "write_authority",
            }
            or grid["type"] != "bounded_source_grid"
            or type(grid["files_observed"]) is not int
            or grid["files_observed"] < 0
            or type(grid["file_hashes"]) is not dict
            or type(grid["definitions"]) is not list
            or grid["runtime_verified"] is not False
            or grid["functional_contracts_verified"] is not False
            or grid["accepted"] is not False
            or grid["write_authority"] != "NONE"
        ):
            raise SourceGridError("invalid grid")

        hashes = grid["file_hashes"]
        if len(hashes) != grid["files_observed"]:
            raise SourceGridError("file count mismatch")

        for file_path, digest in hashes.items():
            if (
                type(file_path) is not str
                or not file_path
                or not file_path.endswith(".py")
                or "\\" in file_path
                or file_path.startswith("/")
                or any(part in ("", ".", "..") for part in file_path.split("/"))
                or type(digest) is not str
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise SourceGridError("invalid file hash record")

        result = {}
        for item in grid["definitions"]:
            if type(item) is not dict or set(item) != {
                "path", "qualified_name", "line",
                "kind", "definition_sha256",
            }:
                raise SourceGridError("malformed definition")

            path = item["path"]
            name = item["qualified_name"]
            line = item["line"]
            kind = item["kind"]
            digest = item["definition_sha256"]

            if (
                type(path) is not str or not path
                or type(name) is not str or not name
                or type(line) is not int or line < 1
                or kind not in ("FUNCTION", "ASYNC_FUNCTION")
                or type(digest) is not str
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise SourceGridError("invalid definition fields")

            if path not in hashes:
                raise SourceGridError("definition source file missing")

            key = (path, name)

            if key in result:
                raise SourceGridError("duplicate qualified identity")

            result[key] = digest

        return result

    old = index(before)
    new = index(after)

    before_lines = {
        (item["path"], item["qualified_name"]): item["line"]
        for item in before["definitions"]
    }
    after_lines = {
        (item["path"], item["qualified_name"]): item["line"]
        for item in after["definitions"]
    }

    moved = sorted(
        key for key in old.keys() & new.keys()
        if before_lines[key] != after_lines[key]
    )

    old_files = before["file_hashes"]
    new_files = after["file_hashes"]

    missing_files = sorted(set(old_files) - set(new_files))
    added_files = sorted(set(new_files) - set(old_files))
    changed_files = sorted(
        path for path in old_files.keys() & new_files.keys()
        if old_files[path] != new_files[path]
    )

    missing = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    changed = sorted(
        key for key in old.keys() & new.keys()
        if old[key] != new[key]
    )

    return {
        "missing": missing,
        "added": added,
        "changed": changed,
        "moved": moved,
        "missing_files": missing_files,
        "added_files": added_files,
        "changed_files": changed_files,
        "same": not (
            missing or added or changed or moved
            or missing_files or added_files or changed_files
        ),
        "source_rechecked": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def verify_source_grid(
    root: Path,
    claimed: dict[str, Any],
    *,
    max_files: int = 1000,
    max_definitions: int = 10000,
    max_file_bytes: int = 1_000_000,
) -> dict[str, Any]:
    """Re-observe source independently of the supplied claim."""
    observed = observe_source_grid(
        root,
        max_files=max_files,
        max_definitions=max_definitions,
        max_file_bytes=max_file_bytes,
    )

    comparison = compare_source_grids(claimed, observed)

    return {
        **comparison,
        "valid": comparison["same"],
        "source_rechecked": True,
        "accepted": False,
        "write_authority": "NONE",
    }
