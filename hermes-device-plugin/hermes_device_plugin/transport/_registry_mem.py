"""In-memory device table — the M0/M1 shape of what becomes `hdp_bridge/registry.py` at M2.

Named to match the eventual `hdp-bridge` module so the M2 extraction is `git mv` plus import
fixes rather than a rewrite (ADR-0004, design §3). Still in-memory and forgotten on restart at
M1 — persistence is explicitly M2's risk, not this milestone's (m1-plan.md §1).
"""

from __future__ import annotations

from .base import DeviceInfo


class RegistryMem:
    """No pairing exists yet (M2) — a device enters this table only by connecting over the wire
    and completing the `hello`/`welcome` handshake (M1), and leaves it (marked offline, not
    removed) when its connection drops."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceInfo] = {}

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    def get(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)

    def register(self, device: DeviceInfo) -> None:
        """Insert or fully replace the entry for `device.device_id` — used both for the initial
        `hello` and for a later `capabilities` full-set replacement (FR-8), which is why this
        overwrites rather than merges."""
        self._devices[device.device_id] = device

    def deregister(self, device_id: str) -> None:
        """Remove the entry entirely. Not used by the normal disconnect path (`mark_offline` is)
        — reserved for an explicit unpair, which has no caller until M2."""
        self._devices.pop(device_id, None)

    def mark_offline(self, device_id: str) -> None:
        """Flip `online` to `False` in place, keeping the entry (and its last-known capability
        list) visible to `device_status_get` rather than making a disconnected device vanish."""
        existing = self._devices.get(device_id)
        if existing is not None and existing.online:
            self._devices[device_id] = DeviceInfo(
                device_id=existing.device_id,
                friendly_name=existing.friendly_name,
                platform=existing.platform,
                online=False,
                capabilities=existing.capabilities,
            )
