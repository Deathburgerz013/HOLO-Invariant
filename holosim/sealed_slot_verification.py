"""Strict verification for sealed SQLite slot databases.

This API deliberately refuses WAL-mode sources. Opening a WAL-mode database
can create ``-wal`` and ``-shm`` files even when the connection is read-only.
Use this strict path only for a quiescent, rollback-journal-mode database
with no SQLite sidecars. Live WAL databases should use the existing
WAL-aware snapshot path, which does not promise source-directory non-mutation.
"""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

from holosim.slot_merkle_sqlite import SlotMerkleDB

_SQLITE_HEADER = b"SQLite format 3\x00"
_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _file_identity(path: Path) -> tuple[int, int, int, int, int]:
    stat = path.stat()
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
    )


def _directory_entries(directory: Path) -> tuple[str, ...]:
    return tuple(sorted(item.name for item in directory.iterdir()))


def _sidecars(path: Path) -> tuple[Path, ...]:
    return tuple(
        candidate
        for suffix in _SIDECAR_SUFFIXES
        if (candidate := Path(str(path) + suffix)).exists()
        or candidate.is_symlink()
    )


def verify_sealed_slot_database(db_path: str | Path) -> dict[str, Any]:
    """Verify a sealed slot database without adding source-directory files.

    Preconditions:
    - The source is an existing, regular SQLite database file.
    - Its SQLite header identifies rollback-journal mode, not WAL mode.
    - No ``-wal``, ``-shm``, or rollback-journal sidecar exists.
    - The source is quiescent for the duration of this operation.

    The function copies a consistent SQLite backup into a private temporary
    directory, verifies that copy, and checks the source file identity and
    source-directory entries before and after access. It never changes the
    source journal mode or deletes source files.

    These checks detect observed changes; they cannot prove that an external
    writer did not change and restore the source between observations. The
    quiescent-source precondition is therefore part of the contract.

    WAL-mode sources are rejected before SQLite opens them. This is important:
    using ``immutable=1`` on a live WAL database can omit committed WAL data.
    """
    source_path = Path(db_path)
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError("source must be an existing regular SQLite file")

    source_path = source_path.resolve()
    source_directory = source_path.parent

    with source_path.open("rb") as handle:
        header = handle.read(100)
    if len(header) < 100 or header[:16] != _SQLITE_HEADER:
        raise ValueError("source is not a valid SQLite database file")

    # SQLite database header bytes 18 and 19 encode the read/write versions:
    # 1 means rollback journal; 2 means WAL. Require rollback mode for this
    # strict no-source-sidecar contract.
    if header[18:20] != b"\x01\x01":
        raise ValueError(
            "strict source-nonmutation verification requires "
            "rollback-journal mode; WAL-mode sources are rejected"
        )

    existing_sidecars = _sidecars(source_path)
    if existing_sidecars:
        names = ", ".join(item.name for item in existing_sidecars)
        raise ValueError(
            f"strict source-nonmutation verification rejects SQLite "
            f"sidecars: {names}"
        )

    initial_identity = _file_identity(source_path)
    initial_entries = _directory_entries(source_directory)

    def assert_source_unchanged() -> None:
        if _file_identity(source_path) != initial_identity:
            raise RuntimeError(
                "source database changed during strict verification"
            )
        if _directory_entries(source_directory) != initial_entries:
            raise RuntimeError(
                "source directory entries changed during strict verification"
            )
        sidecars = _sidecars(source_path)
        if sidecars:
            names = ", ".join(item.name for item in sidecars)
            raise RuntimeError(
                f"SQLite sidecars appeared during strict verification: {names}"
            )

    assert_source_unchanged()

    with tempfile.TemporaryDirectory(prefix="holo-sealed-slot-") as temp:
        snapshot_path = Path(temp) / "snapshot.db"
        source_uri = source_path.as_uri() + "?mode=ro"

        with closing(sqlite3.connect(source_uri, uri=True)) as source:
            source.execute("PRAGMA query_only = ON")
            with closing(sqlite3.connect(str(snapshot_path))) as destination:
                source.backup(destination)

        assert_source_unchanged()

        with SlotMerkleDB(snapshot_path, read_only=True) as verifier:
            result = verifier.verify_chain()

        assert_source_unchanged()
        return result
