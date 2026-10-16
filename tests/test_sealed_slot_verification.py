import sqlite3
from pathlib import Path

import pytest

from holosim.slot_merkle_sqlite import SlotMerkleDB
from holosim.sealed_slot_verification import verify_sealed_slot_database


def _make_sealed_database(db_path: Path) -> None:
    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("sealed verification content", retain_content=True)

    # SlotMerkleDB uses WAL while writing. Convert the closed database to
    # rollback-journal mode before treating it as a sealed source.
    with sqlite3.connect(str(db_path)) as connection:
        mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
    assert mode.lower() == "delete"
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()


def test_sealed_verification_preserves_source_directory_and_content(tmp_path):
    db_path = tmp_path / "sealed.db"
    _make_sealed_database(db_path)

    before_entries = sorted(item.name for item in tmp_path.iterdir())
    before_bytes = db_path.read_bytes()

    result = verify_sealed_slot_database(db_path)

    assert result["status"] == "PASS"
    assert result["entries"] == 1
    assert sorted(item.name for item in tmp_path.iterdir()) == before_entries
    assert db_path.read_bytes() == before_bytes


def test_wal_mode_source_is_rejected_before_sqlite_open(tmp_path):
    db_path = tmp_path / "wal.db"
    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("committed WAL content", retain_content=True)

    before_entries = sorted(item.name for item in tmp_path.iterdir())
    before_bytes = db_path.read_bytes()

    with pytest.raises(ValueError, match="WAL-mode sources are rejected"):
        verify_sealed_slot_database(db_path)

    assert sorted(item.name for item in tmp_path.iterdir()) == before_entries
    assert db_path.read_bytes() == before_bytes


def test_existing_sidecar_is_rejected_without_deletion(tmp_path):
    db_path = tmp_path / "sealed.db"
    _make_sealed_database(db_path)
    sidecar = Path(str(db_path) + "-wal")
    sidecar.write_bytes(b"preserve this existing file")
    before_entries = sorted(item.name for item in tmp_path.iterdir())
    before_sidecar = sidecar.read_bytes()

    with pytest.raises(ValueError, match="rejects SQLite sidecars"):
        verify_sealed_slot_database(db_path)

    assert sorted(item.name for item in tmp_path.iterdir()) == before_entries
    assert sidecar.read_bytes() == before_sidecar


def test_non_sqlite_source_is_rejected_without_directory_changes(tmp_path):
    db_path = tmp_path / "not-sqlite.db"
    db_path.write_bytes(b"not a SQLite database")
    before_entries = sorted(item.name for item in tmp_path.iterdir())
    before_bytes = db_path.read_bytes()

    with pytest.raises(ValueError, match="not a valid SQLite"):
        verify_sealed_slot_database(db_path)

    assert sorted(item.name for item in tmp_path.iterdir()) == before_entries
    assert db_path.read_bytes() == before_bytes


def test_symlink_source_is_rejected(tmp_path):
    target = tmp_path / "target.db"
    _make_sealed_database(target)
    link = tmp_path / "linked.db"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(ValueError, match="regular SQLite file"):
        verify_sealed_slot_database(link)


def test_source_file_mutation_fails_closed(tmp_path, monkeypatch):
    db_path = tmp_path / "sealed.db"
    _make_sealed_database(db_path)

    import holosim.sealed_slot_verification as module

    original_identity = module._file_identity
    calls = 0

    def changed_identity(path):
        nonlocal calls
        calls += 1
        identity = original_identity(path)
        if calls >= 2:
            return (*identity[:-1], identity[-1] + 1)
        return identity

    monkeypatch.setattr(module, "_file_identity", changed_identity)

    with pytest.raises(RuntimeError, match="source database changed"):
        verify_sealed_slot_database(db_path)


def test_source_directory_mutation_fails_closed(tmp_path, monkeypatch):
    db_path = tmp_path / "sealed.db"
    _make_sealed_database(db_path)

    import holosim.sealed_slot_verification as module

    original_entries = module._directory_entries
    calls = 0

    def changed_entries(directory):
        nonlocal calls
        calls += 1
        entries = original_entries(directory)
        if calls >= 2:
            return (*entries, "unexpected-sidecar")
        return entries

    monkeypatch.setattr(module, "_directory_entries", changed_entries)

    with pytest.raises(RuntimeError, match="source directory entries changed"):
        verify_sealed_slot_database(db_path)
