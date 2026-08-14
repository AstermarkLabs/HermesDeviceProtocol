"""In-memory device table — the M0/M1 shape of what becomes `hdp_bridge/registry.py` at M2.

Named to match the eventual `hdp-bridge` module so the M2 extraction is `git mv` plus import
fixes rather than a rewrite (ADR-0004, design §3). At M0 there are zero devices and nothing
pairs one in: this module exists so `inproc.py` has a real (if empty) table to query rather than
a hardcoded `[]` scattered at each call site.
"""

from __future__ import annotations

from .base import DeviceInfo


class RegistryMem:
    """Empty at M0 — no pairing exists yet (M2). `list_devices()` is the one method exercised."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceInfo] = {}

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    def get(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)
