"""Small, component-scoped SQLite schema migration runner.

Legacy databases are adopted additively: existing tables are never dropped. A database
created by a newer ARASH version is rejected before component migrations run, avoiding
an accidental downgrade/write from an older binary.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

Migration = Callable[[sqlite3.Connection], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    component: str,
    target_version: int,
    migrations: dict[int, Migration],
) -> int:
    if not component or target_version < 1:
        raise ValueError("component must be non-empty and target_version must be >= 1")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS arash_schema_versions (
               component TEXT PRIMARY KEY,
               version INTEGER NOT NULL CHECK(version >= 0),
               updated_at TEXT NOT NULL
           )"""
    )
    row = connection.execute(
        "SELECT version FROM arash_schema_versions WHERE component = ?", (component,)
    ).fetchone()
    current = int(row["version"] if row is not None else 0)
    if current > target_version:
        raise RuntimeError(
            f"database schema for {component!r} is newer than this ARASH build "
            f"(database={current}, supported={target_version}); refusing downgrade"
        )

    for next_version in range(current + 1, target_version + 1):
        migration = migrations.get(next_version)
        if migration is None:
            raise RuntimeError(
                f"missing migration {next_version} for database component {component!r}"
            )
        migration(connection)
        connection.execute(
            """INSERT INTO arash_schema_versions(component, version, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(component) DO UPDATE SET
                   version=excluded.version, updated_at=excluded.updated_at""",
            (component, next_version, _utc_now()),
        )
    return target_version
