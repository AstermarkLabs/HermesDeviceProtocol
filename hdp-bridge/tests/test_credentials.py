from __future__ import annotations

from hdp_bridge.credentials import (
    issue_credential,
    revoke_credential,
    verify_credential,
    verify_credential_and_resolve_device,
)
from hdp_bridge.store import db


def test_issued_credential_verifies_and_is_never_stored_in_plaintext(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    credential = issue_credential(conn, "dev_1")
    assert len(credential) >= 32
    stored = conn.execute("SELECT credential_hash FROM credentials").fetchone()[0]
    assert credential not in stored
    assert verify_credential(conn, "dev_1", credential) is True
    assert verify_credential(conn, "dev_1", "wrong") is False


def test_revoked_credential_no_longer_verifies(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    credential = issue_credential(conn, "dev_1")
    revoke_credential(conn, "dev_1")
    assert verify_credential(conn, "dev_1", credential) is False


def test_verify_credential_and_resolve_device_finds_the_owning_device(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    credential = issue_credential(conn, "dev_1")
    assert verify_credential_and_resolve_device(conn, credential) == "dev_1"
    assert verify_credential_and_resolve_device(conn, "wrong") is None


def test_verify_credential_and_resolve_device_ignores_revoked_credentials(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    credential = issue_credential(conn, "dev_1")
    revoke_credential(conn, "dev_1")
    assert verify_credential_and_resolve_device(conn, credential) is None
