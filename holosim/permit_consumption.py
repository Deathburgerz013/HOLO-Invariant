"""Durable, atomic consumption of bounded observation permit identities."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class PermitConsumptionError(RuntimeError):
    """The permit registry could not establish a consumption outcome."""


def consume_permit(
    database_path: str | Path,
    *,
    source_id: str,
    occurrence_id: str,
) -> bool:
    """Atomically claim an occurrence.

    Returns True for the first committed claim, False for a duplicate.
    The caller must verify the signed permit before invoking this function.

    All cooperating executors must use the same durable database.
    """

    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id must be nonempty")
    if not isinstance(occurrence_id, str) or not occurrence_id.strip():
        raise ValueError("occurrence_id must be nonempty")

    path = Path(database_path)

    try:
        with closing(sqlite3.connect(path, timeout=5.0)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS consumed_permits (
                        source_id TEXT NOT NULL,
                        occurrence_id TEXT NOT NULL,
                        PRIMARY KEY (source_id, occurrence_id)
                    )
                    """
                )
                connection.commit()

                cursor = connection.execute(
                    """
                    INSERT INTO consumed_permits (source_id, occurrence_id)
                    VALUES (?, ?)
                    ON CONFLICT(source_id, occurrence_id) DO NOTHING
                    """,
                    (source_id, occurrence_id),
                )

                connection.commit()
                return cursor.rowcount == 1

    except sqlite3.Error as exc:
        raise PermitConsumptionError(
            "permit consumption could not be established"
        ) from exc
