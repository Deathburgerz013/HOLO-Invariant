# Sealed SQLite Source Non-Mutation

## Contract

`verify_sealed_slot_database()` is a strict verification path for a **sealed,
quiescent SQLite slot database**. It creates a private SQLite backup and runs
chain verification against that backup. It does not change the source journal
mode, delete source files, or intentionally create files in the source
directory.

The function checks source identity and source-directory entries before and
after the backup and verification. A detected change fails closed.

## Preconditions

- The source is a regular SQLite database file, not a symlink.
- SQLite header bytes 18 and 19 indicate rollback-journal mode (`1, 1`).
- No `-wal`, `-shm`, or `-journal` sidecar exists beside the source.
- The source is quiescent for the duration of verification.

WAL-mode sources are rejected **before SQLite opens them**. A read-only SQLite
connection to a WAL-mode database may create `-wal` and `-shm` sidecars.
Opening a WAL database with `immutable=1` is not an acceptable workaround:
immutable mode may ignore committed transactions still present in the WAL.

## Concurrency boundary

The source file identity and directory entries are compared before and after
the operation. These checks detect observed changes but cannot prove that an
external process did not modify and restore the source between observations.
The API therefore requires a quiescent source; it is not a lock or a
filesystem snapshot facility.

For live WAL databases, continue using the existing WAL-aware snapshot path.
That path preserves committed WAL data but does not promise that opening the
source has zero filesystem side effects. Do not weaken its WAL consistency
tests to make the strict path appear more general than it is.
