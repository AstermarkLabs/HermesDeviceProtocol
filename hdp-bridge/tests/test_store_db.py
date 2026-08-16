from __future__ import annotations

import sqlite3

import pytest
from hdp_bridge.store import db


def test_connect_creates_schema_and_sets_pragmas(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    assert row[0] == 1
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "devices", "credentials", "pairing_codes", "capabilities",
        "policy_grants", "approvals", "invocations", "schema_version",
    } <= tables
    version_row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert version_row[0] == db.CURRENT_SCHEMA_VERSION


def test_connect_refuses_a_newer_schema_version_than_it_knows(tmp_path):
    db_path = tmp_path / "registry.db"
    db.connect(db_path).close()
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE schema_version SET version = ?", (db.CURRENT_SCHEMA_VERSION + 1,))
    conn.commit()
    conn.close()
    with pytest.raises(db.SchemaTooNewError):
        db.connect(db_path)
