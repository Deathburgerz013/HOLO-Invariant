import sqlite3

import pytest

from holosim.slot_merkle_sqlite import SlotMerkleDB


def test_read_only_missing_database_does_not_create_storage(tmp_path):
    db_path = tmp_path / "missing" / "slots.db"

    with pytest.raises(sqlite3.OperationalError):
        SlotMerkleDB(db_path, read_only=True)

    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_read_only_existing_database_verifies_but_cannot_write(tmp_path):
    db_path = tmp_path / "slots.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("verified test content")

    with SlotMerkleDB(db_path, read_only=True) as reader:
        result = reader.verify_chain()

        assert result["status"] == "PASS"
        assert result["valid"] is True
        assert result["entries"] == 1

        with pytest.raises(sqlite3.OperationalError):
            reader.conn.execute("DELETE FROM slots")

    with SlotMerkleDB(db_path) as writer:
        assert writer.count() == 1
        assert writer.verify_chain()["valid"] is True


def test_verify_chain_detects_tampered_slot_content(tmp_path):
    db_path = tmp_path / "tampered_slots.db"

    with SlotMerkleDB(db_path) as db:
        db.append_slot("original content", retain_content=True)
        assert db.verify_chain()["status"] == "PASS"

        db.conn.execute(
            "UPDATE slots SET content = ? WHERE idx = 1",
            ("tampered content",),
        )
        db.conn.commit()

        result = db.verify_chain()

    assert result["status"] == "FAIL"
    assert result["valid"] is False
    assert any(
        violation["type"] == "content_hash_mismatch"
        and violation["idx"] == 1
        for violation in result["violations"]
    )


@pytest.mark.xfail(
    strict=True,
    reason="Live SQLite read-only mode can create WAL sidecars; "
           "strict source-directory non-mutation is not guaranteed",
)
def test_read_only_verification_does_not_create_sidecars(tmp_path):
    db_path = tmp_path / "slots.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("verified content", retain_content=True)

    wal_path = db_path.with_name(db_path.name + "-wal")
    shm_path = db_path.with_name(db_path.name + "-shm")

    assert not wal_path.exists()
    assert not shm_path.exists()

    with SlotMerkleDB(db_path, read_only=True) as reader:
        result = reader.verify_chain()
        assert result["status"] == "PASS"
        assert not wal_path.exists()
        assert not shm_path.exists()

    assert not wal_path.exists()
    assert not shm_path.exists()


def test_immutable_snapshot_preserves_source_content(tmp_path):
    import hashlib

    db_path = tmp_path / "snapshot.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("snapshot content", retain_content=True)

    original_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()

    with SlotMerkleDB(
        db_path,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        result = reader.verify_chain()

        assert result["status"] == "PASS"
        assert result["entries"] == 1
        assert hashlib.sha256(db_path.read_bytes()).hexdigest() == original_hash

    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == original_hash

    # SQLite may create WAL coordination files during a read-only backup.
    assert {
        path.name for path in tmp_path.iterdir()
    } <= {"snapshot.db", "snapshot.db-wal", "snapshot.db-shm"}

def test_immutable_snapshot_requires_read_only(tmp_path):
    db_path = tmp_path / "snapshot.db"

    with pytest.raises(ValueError, match="requires read_only=True"):
        SlotMerkleDB(db_path, immutable_snapshot=True)

    assert not db_path.exists()


def test_immutable_snapshot_rejects_missing_file(tmp_path):
    db_path = tmp_path / "missing" / "snapshot.db"

    with pytest.raises(ValueError, match="existing regular file"):
        SlotMerkleDB(
            db_path,
            read_only=True,
            immutable_snapshot=True,
        )

    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_immutable_snapshot_detects_existing_content_tampering(tmp_path):
    db_path = tmp_path / "tampered_snapshot.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("original content", retain_content=True)
        writer.conn.execute(
            "UPDATE slots SET content = ? WHERE idx = 1",
            ("tampered content",),
        )
        writer.conn.commit()

    with SlotMerkleDB(
        db_path,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        result = reader.verify_chain()

    assert result["status"] == "FAIL"
    assert result["valid"] is False
    assert any(
        violation["type"] == "content_hash_mismatch"
        and violation["idx"] == 1
        for violation in result["violations"]
    )


def test_immutable_snapshot_accepts_intentionally_unretained_content(tmp_path):
    db_path = tmp_path / "unretained_snapshot.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot(
            "content deliberately not retained",
            retain_content=False,
        )

        row = writer.conn.execute(
            "SELECT content, content_hash FROM slots WHERE idx = 1"
        ).fetchone()

        assert row["content"] is None
        assert isinstance(row["content_hash"], str)

    with SlotMerkleDB(
        db_path,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        result = reader.verify_chain()

    assert result["status"] == "PASS"
    assert result["entries"] == 1
    assert result["violations"] == []


def test_cli_verify_missing_database_fails_without_creation(tmp_path):
    import subprocess
    import sys

    db_path = tmp_path / "missing" / "slots.db"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holosim.slot_merkle_sqlite",
            "--db",
            str(db_path),
            "verify",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_immutable_sqlite_open_can_ignore_committed_wal(tmp_path):
    import sqlite3

    db_path = tmp_path / "wal_visibility.db"

    writer = sqlite3.connect(str(db_path))
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE evidence (value TEXT)")
        writer.commit()
        writer.execute("INSERT INTO evidence VALUES ('committed_in_wal')")
        writer.commit()

        assert (tmp_path / "wal_visibility.db-wal").exists()
        assert writer.execute(
            "SELECT COUNT(*) FROM evidence"
        ).fetchone()[0] == 1

        immutable = sqlite3.connect(
            db_path.resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
        )
        try:
            try:
                count = immutable.execute(
                    "SELECT COUNT(*) FROM evidence"
                ).fetchone()[0]
            except sqlite3.OperationalError as error:
                assert "no such table" in str(error)
            else:
                assert count == 0
        finally:
            immutable.close()
    finally:
        writer.close()


def test_immutable_snapshot_captures_active_wal(tmp_path):
    from pathlib import Path
    import sqlite3
    from holosim.slot_merkle_sqlite import SlotMerkleDB

    db_path = tmp_path / "active_wal.db"
    writer = sqlite3.connect(str(db_path))

    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE evidence (value TEXT)")
        writer.execute("INSERT INTO evidence VALUES ('committed')")
        writer.commit()

        assert Path(str(db_path) + "-wal").exists()

        with SlotMerkleDB(
            db_path, read_only=True, immutable_snapshot=True
        ) as reader:
            captured = reader.conn.execute(
                "SELECT value FROM evidence"
            ).fetchall()

        assert [row[0] for row in captured] == ["committed"]
    finally:
        writer.close()


def test_immutable_snapshot_captures_wal_created_during_open(
    tmp_path, monkeypatch
):
    from pathlib import Path
    import sqlite3
    from holosim import slot_merkle_sqlite as module

    db_path = tmp_path / "race.db"

    with sqlite3.connect(str(db_path)) as connection:
        connection.execute("CREATE TABLE evidence (value TEXT)")
        connection.commit()

    original_connect = sqlite3.connect
    writer = None

    def racing_connect(database, *args, **kwargs):
        nonlocal writer

        if (
            kwargs.get("uri")
            and "mode=ro" in str(database)
            and "immutable=1" not in str(database)
            and writer is None
        ):
            writer = original_connect(str(db_path))
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute(
                "INSERT INTO evidence VALUES ('committed_during_open')"
            )
            writer.commit()
            assert Path(str(db_path) + "-wal").exists()

        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(module.sqlite3, "connect", racing_connect)

    try:
        with module.SlotMerkleDB(
            db_path, read_only=True, immutable_snapshot=True
        ) as reader:
            captured = reader.conn.execute(
                "SELECT value FROM evidence"
            ).fetchall()

        assert [row[0] for row in captured] == [
            "committed_during_open"
        ]
    finally:
        if writer is not None:
            writer.close()


def test_sqlite_backup_snapshot_isolated_from_later_wal_writes(tmp_path):
    import sqlite3
    from contextlib import closing

    source_path = tmp_path / "live.db"
    snapshot_path = tmp_path / "snapshot_copy.db"

    with closing(sqlite3.connect(str(source_path))) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE evidence (value TEXT)")
        writer.execute("INSERT INTO evidence VALUES ('before_backup')")
        writer.commit()

        assert (tmp_path / "live.db-wal").exists()

        with closing(sqlite3.connect(str(snapshot_path))) as destination:
            writer.backup(destination)

        writer.execute("INSERT INTO evidence VALUES ('after_backup')")
        writer.commit()

        with closing(sqlite3.connect(
            snapshot_path.resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
        )) as reader:
            assert writer.execute(
                "SELECT value FROM evidence ORDER BY rowid"
            ).fetchall() == [
                ("before_backup",),
                ("after_backup",),
            ]

            assert reader.execute(
                "SELECT value FROM evidence ORDER BY rowid"
            ).fetchall() == [
                ("before_backup",),
            ]

            assert not (tmp_path / "snapshot_copy.db-wal").exists()
            assert not (tmp_path / "snapshot_copy.db-shm").exists()


def test_read_only_sqlite_backup_includes_committed_wal(tmp_path):
    import sqlite3
    from contextlib import closing

    source_path = tmp_path / "source.db"
    snapshot_path = tmp_path / "snapshot.db"

    with closing(sqlite3.connect(str(source_path))) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE evidence (value TEXT)")
        writer.execute("INSERT INTO evidence VALUES ('committed')")
        writer.commit()

        assert (tmp_path / "source.db-wal").exists()

        with closing(sqlite3.connect(
            source_path.resolve().as_uri() + "?mode=ro",
            uri=True,
        )) as reader:
            with closing(sqlite3.connect(str(snapshot_path))) as destination:
                reader.backup(destination)

        with closing(sqlite3.connect(
            snapshot_path.resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
        )) as verifier:
            assert verifier.execute(
                "SELECT value FROM evidence"
            ).fetchall() == [("committed",)]

        assert not (tmp_path / "snapshot.db-wal").exists()
        assert not (tmp_path / "snapshot.db-shm").exists()


def test_create_slot_snapshot_captures_wal_and_preserves_source(tmp_path):
    from holosim.slot_merkle_sqlite import create_slot_snapshot

    source_path = tmp_path / "live.db"
    snapshot_path = tmp_path / "snapshot.db"

    with SlotMerkleDB(source_path) as writer:
        writer.append_slot("before backup", retain_content=True)

        assert (tmp_path / "live.db-wal").exists()

        create_slot_snapshot(source_path, snapshot_path)

        writer.append_slot("after backup", retain_content=True)
        assert writer.count() == 2

    with SlotMerkleDB(
        snapshot_path,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        result = reader.verify_chain()
        assert result["status"] == "PASS"
        assert result["entries"] == 1

    # Read-only SQLite backup may create WAL coordination files.
    # Only the expected database and its SQLite sidecars are permitted.
    assert {
        path.name for path in tmp_path.iterdir()
    } <= {
        "live.db", "live.db-wal", "live.db-shm",
        "snapshot.db", "snapshot.db-wal", "snapshot.db-shm",
    }

    with pytest.raises(FileExistsError):
        create_slot_snapshot(source_path, snapshot_path)


def test_create_slot_snapshot_cleans_up_failed_backup(tmp_path, monkeypatch):
    import sqlite3
    import pytest
    from holosim import slot_merkle_sqlite as module

    source_path = tmp_path / "source.db"
    snapshot_path = tmp_path / "snapshot.db"

    with module.SlotMerkleDB(source_path) as writer:
        writer.append_slot("preserve source", retain_content=True)

    original_connect = sqlite3.connect

    class FailingBackup:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, *args, **kwargs):
            return self.connection.execute(*args, **kwargs)

        def backup(self, destination):
            raise sqlite3.OperationalError("simulated backup failure")

        def close(self):
            self.connection.close()

    def failing_connect(database, *args, **kwargs):
        connection = original_connect(database, *args, **kwargs)
        if kwargs.get("uri") and "mode=ro" in str(database):
            return FailingBackup(connection)
        return connection

    monkeypatch.setattr(module.sqlite3, "connect", failing_connect)

    with pytest.raises(sqlite3.OperationalError, match="simulated backup failure"):
        module.create_slot_snapshot(source_path, snapshot_path)

    assert source_path.exists()
    assert not snapshot_path.exists()

    # Restore SQLite before independently verifying the surviving source.
    monkeypatch.setattr(module.sqlite3, "connect", original_connect)

    with module.SlotMerkleDB(source_path, read_only=True) as reader:
        assert reader.verify_chain()["status"] == "PASS"


def test_create_slot_snapshot_does_not_delete_replaced_destination(
    tmp_path, monkeypatch
):
    import sqlite3
    import pytest
    from holosim import slot_merkle_sqlite as module

    source_path = tmp_path / "source.db"
    destination_path = tmp_path / "snapshot.db"
    with module.SlotMerkleDB(source_path) as writer:
        writer.append_slot("preserved source", retain_content=True)

    original_connect = sqlite3.connect

    def interfering_connect(database, *args, **kwargs):
        if kwargs.get("uri") and "mode=ro" in str(database):
            destination_path.write_bytes(b"EXTERNAL FILE")
            raise sqlite3.OperationalError("simulated interference")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(module.sqlite3, "connect", interfering_connect)

    with pytest.raises(sqlite3.OperationalError, match="simulated interference"):
        module.create_slot_snapshot(source_path, destination_path)

    assert destination_path.read_bytes() == b"EXTERNAL FILE"
    assert source_path.exists()


def test_create_slot_snapshot_rejects_competing_publication(
    tmp_path, monkeypatch
):
    import os
    import pytest
    from holosim import slot_merkle_sqlite as module

    source_path = tmp_path / "source.db"
    destination_path = tmp_path / "snapshot.db"

    with module.SlotMerkleDB(source_path) as writer:
        writer.append_slot("original evidence", retain_content=True)

    original_link = os.link

    def competing_link(source, destination, *args, **kwargs):
        destination_path.write_bytes(b"COMPETING FILE")
        return original_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "link", competing_link)

    with pytest.raises(FileExistsError):
        module.create_slot_snapshot(source_path, destination_path)

    assert destination_path.read_bytes() == b"COMPETING FILE"
    assert source_path.exists()
    assert not list(tmp_path.glob(".slot-snapshot-*"))



def test_create_slot_snapshot_fails_closed_when_hard_link_unsupported(
    tmp_path, monkeypatch
):
    import errno
    import os
    import pytest
    from holosim import slot_merkle_sqlite as module

    source_path = tmp_path / "source.db"
    destination_path = tmp_path / "snapshot.db"

    with module.SlotMerkleDB(source_path) as writer:
        writer.append_slot("original evidence", retain_content=True)

    def unsupported_link(source, destination, *args, **kwargs):
        raise OSError(errno.EXDEV, "simulated cross-device link")

    monkeypatch.setattr(os, "link", unsupported_link)

    with pytest.raises(OSError) as error:
        module.create_slot_snapshot(source_path, destination_path)

    assert error.value.errno == errno.EXDEV
    assert source_path.exists()
    assert not destination_path.exists()
    assert not list(tmp_path.glob(".slot-snapshot-*"))

def test_immutable_snapshot_captures_state_before_first_read(tmp_path):
    import sqlite3
    from holosim.slot_merkle_sqlite import SlotMerkleDB

    db_path = tmp_path / "changing.db"

    with sqlite3.connect(str(db_path)) as writer:
        writer.execute("CREATE TABLE evidence (value TEXT)")
        writer.execute("INSERT INTO evidence VALUES ('before')")
        writer.commit()

    with SlotMerkleDB(
        db_path,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        with sqlite3.connect(str(db_path)) as writer:
            writer.execute("INSERT INTO evidence VALUES ('after')")
            writer.commit()

        observed = reader.conn.execute(
            "SELECT value FROM evidence ORDER BY rowid"
        ).fetchall()

        assert [row[0] for row in observed] == ["before"]


def test_immutable_snapshot_cleans_up_failed_final_open(
    tmp_path, monkeypatch
):
    from pathlib import Path
    import sqlite3
    import tempfile
    import pytest
    from holosim import slot_merkle_sqlite as module

    db_path = tmp_path / "source.db"

    with module.SlotMerkleDB(db_path) as writer:
        writer.append_slot("retained evidence", retain_content=True)

    original_connect = sqlite3.connect
    original_tempdir = tempfile.TemporaryDirectory
    directories = []

    def tracked_tempdir(*args, **kwargs):
        directory = original_tempdir(*args, **kwargs)
        directories.append(Path(directory.name))
        return directory

    def failing_connect(database, *args, **kwargs):
        if kwargs.get("uri") and "immutable=1" in str(database):
            raise sqlite3.OperationalError("simulated final open failure")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(tempfile, "TemporaryDirectory", tracked_tempdir)
    monkeypatch.setattr(module.sqlite3, "connect", failing_connect)

    with pytest.raises(
        sqlite3.OperationalError, match="simulated final open failure"
    ):
        module.SlotMerkleDB(
            db_path, read_only=True, immutable_snapshot=True
        )

    assert len(directories) == 1
    assert not directories[0].exists()
    assert db_path.exists()


def test_immutable_snapshot_cleans_up_after_normal_close(tmp_path):
    from pathlib import Path
    from holosim.slot_merkle_sqlite import SlotMerkleDB

    db_path = tmp_path / "source.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("retained evidence", retain_content=True)

    with SlotMerkleDB(
        db_path, read_only=True, immutable_snapshot=True
    ) as reader:
        directory = Path(reader._snapshot_directory.name)
        assert directory.is_dir()
        assert reader.verify_chain()["status"] == "PASS"

    assert not directory.exists()


def test_immutable_snapshot_rejects_source_replacement(
    tmp_path, monkeypatch
):
    import pytest
    from pathlib import Path
    from holosim import slot_merkle_sqlite as module

    source = tmp_path / "source.db"
    replacement = tmp_path / "replacement.db"

    with module.SlotMerkleDB(source) as writer:
        writer.append_slot("original", retain_content=True)

    with module.SlotMerkleDB(replacement) as writer:
        writer.append_slot("replacement", retain_content=True)

    original_resolve = Path.resolve
    replaced = False

    def racing_resolve(path, *args, **kwargs):
        nonlocal replaced

        if path == source and not replaced:
            replaced = True
            source.unlink()
            replacement.replace(source)

        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", racing_resolve)

    with pytest.raises(
        (ValueError, OSError),
        match="source|changed|replacement",
    ):
        with module.SlotMerkleDB(
            source, read_only=True, immutable_snapshot=True
        ):
            pass

    assert replaced


def test_immutable_snapshot_rejects_mismatched_opened_database(
    tmp_path, monkeypatch
):
    import sqlite3
    import pytest
    from holosim import slot_merkle_sqlite as module

    source = tmp_path / "source.db"
    alternate = tmp_path / "alternate.db"

    with module.SlotMerkleDB(source) as writer:
        writer.append_slot("expected", retain_content=True)

    with module.SlotMerkleDB(alternate) as writer:
        writer.append_slot("unexpected", retain_content=True)

    original_connect = sqlite3.connect
    substituted = False

    def redirected_connect(database, *args, **kwargs):
        nonlocal substituted

        if (
            not substituted
            and kwargs.get("uri")
            and str(database) == source.resolve().as_uri() + "?mode=ro"
        ):
            substituted = True
            database = alternate.resolve().as_uri() + "?mode=ro"

        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(module.sqlite3, "connect", redirected_connect)

    with pytest.raises(
        (ValueError, OSError),
        match="source|identity|mismatch|changed",
    ):
        with module.SlotMerkleDB(
            source, read_only=True, immutable_snapshot=True
        ):
            pass

    assert substituted


def test_immutable_snapshot_windows_drive_and_spaces(tmp_path):
    import os
    from pathlib import Path

    import pytest
    from holosim.slot_merkle_sqlite import SlotMerkleDB

    if os.name != "nt":
        pytest.skip("Windows-specific path regression")

    directory = tmp_path / "holo sqlite path test"
    directory.mkdir()
    source = directory / "slot ledger.db"

    assert source.drive
    assert " " in str(source)

    with SlotMerkleDB(source) as writer:
        writer.append_slot("windows-path-test", retain_content=True)
        expected_root = writer.get_current_root()

    with SlotMerkleDB(
        source,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        assert reader.count() == 1
        assert reader.get_current_root() == expected_root

    assert source.exists()

@pytest.mark.xfail(
    strict=True,
    reason="Private snapshot verification can create source WAL/SHM sidecars",
)
def test_immutable_snapshot_does_not_create_source_sidecars(tmp_path):
    db_path = tmp_path / "snapshot_sidecars.db"

    with SlotMerkleDB(db_path) as writer:
        writer.append_slot("verified content", retain_content=True)

    wal_path = db_path.with_name(db_path.name + "-wal")
    shm_path = db_path.with_name(db_path.name + "-shm")

    assert not wal_path.exists()
    assert not shm_path.exists()

    with SlotMerkleDB(
        db_path,
        read_only=True,
        immutable_snapshot=True,
    ) as reader:
        assert reader.verify_chain()["status"] == "PASS"

    assert not wal_path.exists()
    assert not shm_path.exists()

def test_immutable_snapshot_rejects_identity_change_after_backup(
    tmp_path, monkeypatch
):
    from holosim import slot_merkle_sqlite as module

    source = tmp_path / "source.db"

    with module.SlotMerkleDB(source) as writer:
        writer.append_slot("original", retain_content=True)

    original_connect = sqlite3.connect
    original_stat = type(source).stat
    backup_completed = False

    class BackupBoundary:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, *args, **kwargs):
            return self.connection.execute(*args, **kwargs)

        def backup(self, destination):
            nonlocal backup_completed
            self.connection.backup(destination)
            backup_completed = True

        def close(self):
            self.connection.close()

    def intercepted_connect(database, *args, **kwargs):
        connection = original_connect(database, *args, **kwargs)
        if kwargs.get("uri") and str(database) == source.resolve().as_uri() + "?mode=ro":
            return BackupBoundary(connection)
        return connection

    def changed_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path == source and backup_completed:
            from types import SimpleNamespace
            return SimpleNamespace(
                st_dev=result.st_dev,
                st_ino=result.st_ino + 1,
            )
        return result

    monkeypatch.setattr(module.sqlite3, "connect", intercepted_connect)
    monkeypatch.setattr(type(source), "stat", changed_stat)

    with pytest.raises(ValueError, match="source.*changed|identity"):
        with module.SlotMerkleDB(
            source, read_only=True, immutable_snapshot=True
        ):
            pass

    assert backup_completed
def test_create_slot_snapshot_rejects_successful_invalid_backup(tmp_path, monkeypatch):
    import sqlite3

    import pytest

    from holosim import slot_merkle_sqlite as module

    source_path = tmp_path / "source.db"
    snapshot_path = tmp_path / "snapshot.db"

    with module.SlotMerkleDB(source_path) as writer:
        writer.append_slot("preserve source", retain_content=True)

    original_connect = sqlite3.connect

    class InvalidBackup:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, *args, **kwargs):
            return self.connection.execute(*args, **kwargs)

        def backup(self, destination):
            # Simulate a broken backup provider reporting success
            # without copying the source database.
            return None

        def close(self):
            self.connection.close()

    def invalid_connect(database, *args, **kwargs):
        connection = original_connect(database, *args, **kwargs)
        if kwargs.get("uri") and "mode=ro" in str(database):
            return InvalidBackup(connection)
        return connection

    monkeypatch.setattr(module.sqlite3, "connect", invalid_connect)

    with pytest.raises(Exception):
        module.create_slot_snapshot(source_path, snapshot_path)

    assert not snapshot_path.exists()

    monkeypatch.setattr(module.sqlite3, "connect", original_connect)

    with module.SlotMerkleDB(source_path, read_only=True) as reader:
        assert reader.verify_chain()["status"] == "PASS"

def test_create_slot_snapshot_rejects_successful_valid_prefix_backup(
    tmp_path, monkeypatch
):
    import sqlite3

    import pytest

    from holosim import slot_merkle_sqlite as module

    source_path = tmp_path / "source.db"
    prefix_path = tmp_path / "valid-prefix.db"
    snapshot_path = tmp_path / "snapshot.db"

    # Construct a valid one-slot prefix independently.
    with module.SlotMerkleDB(prefix_path) as prefix:
        prefix.append_slot("first", retain_content=True)
        assert prefix.verify_chain()["status"] == "PASS"

    # The actual source has two committed slots.
    with module.SlotMerkleDB(source_path) as writer:
        writer.append_slot("first", retain_content=True)
        writer.append_slot("second", retain_content=True)
        assert writer.count() == 2
        assert writer.verify_chain()["status"] == "PASS"

    original_connect = sqlite3.connect

    class PrefixBackup:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, *args, **kwargs):
            return self.connection.execute(*args, **kwargs)

        def backup(self, destination):
            # Fault injection: return success after copying an
            # internally valid but incomplete database.
            with original_connect(str(prefix_path)) as prefix:
                prefix.backup(destination)

        def close(self):
            self.connection.close()

    def intercepted_connect(database, *args, **kwargs):
        connection = original_connect(database, *args, **kwargs)
        if (
            kwargs.get("uri")
            and str(database) == source_path.resolve().as_uri() + "?mode=ro"
        ):
            return PrefixBackup(connection)
        return connection

    monkeypatch.setattr(module.sqlite3, "connect", intercepted_connect)

    with pytest.raises(ValueError, match="incomplete|mismatch"):
        module.create_slot_snapshot(source_path, snapshot_path)

    assert not snapshot_path.exists()
