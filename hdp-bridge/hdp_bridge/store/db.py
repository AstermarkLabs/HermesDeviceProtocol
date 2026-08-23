"""SQLite connection factory and forward-only migration runner (§3.1, §3.2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
CURRENT_SCHEMA_VERSION = 2


class SchemaTooNewError(RuntimeError):
    """The database's `schema_version` is higher than this build of `hdp_bridge` knows — refuse
    to start rather than silently downgrading a newer daemon's data (§3.1)."""


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")


def _migrate(conn: sqlite3.Connection) -> None:
    has_version_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    current = 0
    if has_version_table:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        current = row[0] if row else 0
    if current > CURRENT_SCHEMA_VERSION:
        raise SchemaTooNewError(
            f"database schema_version={current} is newer than this build supports "
            f"({CURRENT_SCHEMA_VERSION})"
        )
    for migration_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        number = int(migration_path.stem.split("_", 1)[0])
        if number <= current:
            continue
        with conn:
            conn.executescript(migration_path.read_text())


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _apply_pragmas(conn)
    _migrate(conn)
    return conn
