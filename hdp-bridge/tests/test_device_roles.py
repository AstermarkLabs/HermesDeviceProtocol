from __future__ import annotations

import pytest
from hdp_bridge.device_roles import DeviceRoleError, DeviceRoleManager
from hdp_bridge.store import db


def _device(conn, device_id: str, role: str) -> None:
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state, role) VALUES (?, ?, '', '', 0, 0, 'active', ?)",
        (device_id, device_id, role),
    )


def test_promotion_leaves_exactly_one_primary(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    _device(conn, "old", "primary")
    _device(conn, "new", "secondary")

    DeviceRoleManager(conn).promote("new")

    primary = conn.execute("SELECT device_id FROM devices WHERE role = 'primary'").fetchone()[0]
    old_role = conn.execute("SELECT role FROM devices WHERE device_id = 'old'").fetchone()[0]
    assert primary == "new"
    assert old_role == "secondary"


def test_unknown_promotion_is_refused(tmp_path):
    with pytest.raises(DeviceRoleError):
        DeviceRoleManager(db.connect(tmp_path / "registry.db")).promote("missing")


def test_primary_removal_requires_no_active_secondary(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    _device(conn, "primary", "primary")
    manager = DeviceRoleManager(conn)
    assert manager.may_remove_primary("primary") is True
    _device(conn, "secondary", "secondary")
    assert manager.may_remove_primary("primary") is False


def test_removing_a_lone_primary_leaves_the_profile_ready_for_usb_recovery(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    _device(conn, "primary", "primary")

    DeviceRoleManager(conn).remove_primary("primary")

    assert conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0


def test_removing_primary_with_secondaries_is_refused(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    _device(conn, "primary", "primary")
    _device(conn, "secondary", "secondary")

    with pytest.raises(DeviceRoleError, match="promote a secondary"):
        DeviceRoleManager(conn).remove_primary("primary")
