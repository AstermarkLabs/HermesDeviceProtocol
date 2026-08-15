"""Value types owned by the daemon. Deliberately not shared with `hermes_device_plugin` — see
this plan's Global Constraints on import direction. Small dataclasses; duplicating a handful of
fields across two independently-deployable packages costs nothing and avoids a backwards
dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityRecord:
    name: str
    version: int

    def to_wire(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    friendly_name: str
    platform: str
    online: bool
    client_version: str = ""
    state: str = "active"
    first_paired_at: int = 0
    last_seen_at: int = 0
    capabilities: list[CapabilityRecord] = field(default_factory=list)

    def to_wire(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "friendly_name": self.friendly_name,
            "platform": self.platform,
            "client_version": self.client_version,
            "online": self.online,
            "state": self.state,
            "first_paired_at": self.first_paired_at,
            "last_seen_at": self.last_seen_at,
            "capabilities": [c.to_wire() for c in self.capabilities],
        }
