"""Atomic role transitions for the single-primary sentinel model."""

from __future__ import annotations

import sqlite3


class DeviceRoleError(RuntimeError):
    """A requested primary/secondary transition violates the sentinel invariant."""


class DeviceRoleManager:
    """Apply owner-authorized role changes without ever exposing two primaries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def promote(self, device_id: str) -> None:
        """Promote an existing secondary, atomically demoting the old primary."""
        with self._conn:
            candidate = self._conn.execute(
                "SELECT role FROM devices WHERE device_id = ? AND state = 'active'", (device_id,)
            ).fetchone()
            if candidate is None:
                raise DeviceRoleError("device is not an active enrolled device")
            if candidate[0] == "primary":
                return
            self._conn.execute("UPDATE devices SET role = 'secondary' WHERE role = 'primary'")
            cursor = self._conn.execute(
                "UPDATE devices SET role = 'primary' WHERE device_id = ? AND role = 'secondary'",
                (device_id,),
            )
            if cursor.rowcount != 1:  # pragma: no cover - transaction guards the only race here.
                raise DeviceRoleError("unable to promote device")

    def may_remove_primary(self, device_id: str) -> bool:
        """Only a lone primary may be removed; otherwise a replacement must be promoted first."""
        role = self._conn.execute(
            "SELECT role FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        if role is None or role[0] != "primary":
            return True
        secondary = self._conn.execute(
            "SELECT 1 FROM devices WHERE role = 'secondary' AND state = 'active'"
        ).fetchone()
        return secondary is None

    def remove_primary(self, device_id: str) -> None:
        """Remove a lone primary; callers must perform fresh owner authorization first."""
        with self._conn:
            row = self._conn.execute(
                "SELECT role FROM devices WHERE device_id = ? AND state = 'active'", (device_id,)
            ).fetchone()
            if row is None or row[0] != "primary":
                raise DeviceRoleError("device is not the active primary")
            if not self.may_remove_primary(device_id):
                raise DeviceRoleError("promote a secondary before removing the primary")
            self._conn.execute("DELETE FROM capabilities WHERE device_id = ?", (device_id,))
            self._conn.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
