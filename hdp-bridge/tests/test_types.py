from __future__ import annotations

from hdp_bridge.types import CapabilityRecord, DeviceRecord


def test_device_record_round_trips_through_wire_dict():
    record = DeviceRecord(
        device_id="dev_01",
        friendly_name="workshop-node",
        platform="linux",
        client_version="0.1.0",
        online=True,
        state="active",
        first_paired_at=1000,
        last_seen_at=2000,
        capabilities=[CapabilityRecord(name="diagnostics.echo", version=1)],
    )
    wire = record.to_wire()
    assert wire == {
        "device_id": "dev_01",
        "friendly_name": "workshop-node",
        "platform": "linux",
        "client_version": "0.1.0",
        "online": True,
        "state": "active",
        "first_paired_at": 1000,
        "last_seen_at": 2000,
        "capabilities": [{"name": "diagnostics.echo", "version": 1}],
    }
