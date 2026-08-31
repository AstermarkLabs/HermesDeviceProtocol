from __future__ import annotations

import sqlite3
from pathlib import Path

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
        "devices",
        "credentials",
        "pairing_codes",
        "capabilities",
        "policy_grants",
        "approvals",
        "invocations",
        "schema_version",
    } <= tables
    version_row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert version_row[0] == db.CURRENT_SCHEMA_VERSION


def test_connect_creates_usb_sentinel_pairing_schema(tmp_path):
    conn = db.connect(tmp_path / "registry.db")

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"pending_enrollments", "pairing_locks"} <= tables

    device_columns = {row[1] for row in conn.execute("PRAGMA table_info(devices)")}
    assert "role" in device_columns

    indexes = {row[1] for row in conn.execute("PRAGMA index_list(devices)")}
    assert "one_primary_device" in indexes


def test_connect_refuses_a_newer_schema_version_than_it_knows(tmp_path):
    db_path = tmp_path / "registry.db"
    db.connect(db_path).close()
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE schema_version SET version = ?", (db.CURRENT_SCHEMA_VERSION + 1,))
    conn.commit()
    conn.close()
    with pytest.raises(db.SchemaTooNewError):
        db.connect(db_path)


def test_migrating_a_populated_v1_database_preserves_rows_and_defaults(tmp_path):
    """The user's live registry is a populated v1 database — the first one migration 002 will
    ever touch. A fresh-tmpdir migration proves nothing about that path."""
    db_path = tmp_path / "registry.db"
    raw = sqlite3.connect(db_path)
    raw.executescript((Path(db.__file__).parent / "migrations" / "001_initial.sql").read_text())
    raw.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES "
        "('dev_legacy', 'workshop', 'linux', '1.0', 10, 20, 'active')"
    )
    raw.execute(
        "INSERT INTO pairing_codes (code_hash, created_at, expires_at, consumed_at, "
        "issued_device_id) VALUES ('abc123', 1, 2, NULL, NULL)"
    )
    raw.commit()
    raw.close()

    conn = db.connect(db_path)

    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 4
    device = conn.execute(
        "SELECT friendly_name, platform, device_pubkey, role FROM devices "
        "WHERE device_id = 'dev_legacy'"
    ).fetchone()
    # Existing data survives and all previously enrolled devices start as secondaries.
    assert device == ("workshop", "linux", "", "secondary")
    code = conn.execute(
        "SELECT attempts_remaining, invalidated_at FROM pairing_codes WHERE code_hash = 'abc123'"
    ).fetchone()
    assert code == (5, None)


def test_migrating_an_already_current_database_is_a_no_op(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state, device_pubkey) VALUES "
        "('dev_1', 'n', 'android', '', 0, 0, 'active', 'a-key')"
    )
    conn.commit()
    conn.close()

    reopened = db.connect(db_path)
    assert reopened.execute("SELECT version FROM schema_version").fetchone()[0] == 4
    assert (
        reopened.execute("SELECT device_pubkey FROM devices WHERE device_id = 'dev_1'").fetchone()[
            0
        ]
        == "a-key"
    )
