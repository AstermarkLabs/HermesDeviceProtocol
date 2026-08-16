"""SQLite-backed device registry (§3, §3.1). `online` state is never persisted — it is
process-lifetime information (§4.6): a device is online exactly while its `NodeConnection` is
live, which cannot survive a daemon restart regardless of what the database says."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .store import db
from .types import CapabilityRecord, DeviceRecord


class Registry:
    """No pairing exists yet (M2 pairing work) — a device enters this table only by connecting
    over the wire and completing the `hello`/`welcome` handshake, and leaves it (marked offline,
    not removed) when its connection drops."""

    def __init__(self, db_path: Path) -> None:
        self._conn = db.connect(db_path)

    def list_devices(self) -> list[DeviceRecord]:
        rows = self._conn.execute(
            "SELECT device_id, friendly_name, platform, client_version, first_paired_at, "
            "last_seen_at, state FROM devices"
        ).fetchall()
        return [self._to_record(row) for row in rows]

    def get(self, device_id: str) -> DeviceRecord | None:
        row = self._conn.execute(
            "SELECT device_id, friendly_name, platform, client_version, first_paired_at, "
            "last_seen_at, state FROM devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        return self._to_record(row) if row else None

    def _to_record(self, row: tuple) -> DeviceRecord:
        device_id = row[0]
        caps = self._conn.execute(
            "SELECT name, version, input_schema, output_schema FROM capabilities "
            "WHERE device_id = ?",
            (device_id,),
        ).fetchall()
        return DeviceRecord(
            device_id=device_id,
            friendly_name=row[1],
            platform=row[2],
            client_version=row[3],
            first_paired_at=row[4],
            last_seen_at=row[5],
            state=row[6],
            online=False,  # caller overlays live online state — done in control.py's
            # `_ctl_list_devices` (Task 6), via `record.device_id in self._connections`.
            capabilities=[
                CapabilityRecord(
                    name=c[0],
                    version=c[1],
                    input_schema=json.loads(c[2]),
                    output_schema=json.loads(c[3]),
                )
                for c in caps
            ],
        )

    def register(self, device: DeviceRecord) -> None:
        """Insert-or-replace the device row and fully replace its capability set (FR-8's
        full-replacement rule, now persisted)."""
        now_ms = int(time.time() * 1000)
        with self._conn:
            existing = self._conn.execute(
                "SELECT first_paired_at FROM devices WHERE device_id = ?", (device.device_id,)
            ).fetchone()
            first_paired_at = existing[0] if existing else (device.first_paired_at or now_ms)
            self._conn.execute(
                "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
                "first_paired_at, last_seen_at, state) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET friendly_name=excluded.friendly_name, "
                "platform=excluded.platform, client_version=excluded.client_version, "
                "last_seen_at=excluded.last_seen_at, state=excluded.state",
                (
                    device.device_id,
                    device.friendly_name,
                    device.platform,
                    device.client_version,
                    first_paired_at,
                    device.last_seen_at or now_ms,
                    device.state,
                ),
            )
            self._conn.execute("DELETE FROM capabilities WHERE device_id = ?", (device.device_id,))
            for cap in device.capabilities:
                self._conn.execute(
                    "INSERT INTO capabilities (device_id, name, version, input_schema, "
                    "output_schema, advertised_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        device.device_id,
                        cap.name,
                        cap.version,
                        json.dumps(cap.input_schema),
                        json.dumps(cap.output_schema),
                        now_ms,
                    ),
                )

    def deregister(self, device_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM capabilities WHERE device_id = ?", (device_id,))
            self._conn.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))

    def mark_offline(self, device_id: str) -> None:
        # `online` is not a column (see class docstring) — this becomes a no-op on the durable
        # side; the caller (connection.py's in-memory `_connections` dict removal) is what
        # actually changes online state. Kept as a method for API-compatibility with the
        # pre-SQLite RegistryMem call sites, and as the place `last_seen_at`'s final value gets
        # written before the row goes quiet.
        with self._conn:
            self._conn.execute(
                "UPDATE devices SET last_seen_at = ? WHERE device_id = ?",
                (int(time.time() * 1000), device_id),
            )
