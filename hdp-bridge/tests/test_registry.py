"""`Registry` in isolation — no server, no socket, no node. SQLite-backed (`store/db.py`); each
test gets its own `tmp_path`-scoped database file."""

from __future__ import annotations

from hdp_bridge.registry import Registry
from hdp_bridge.types import CapabilityRecord, DeviceRecord


def _device(device_id: str = "dev_01", *, online: bool = True) -> DeviceRecord:
    return DeviceRecord(
        device_id=device_id,
        friendly_name="workshop-node",
        platform="linux",
        online=online,
        capabilities=[CapabilityRecord(name="diagnostics.echo", version=1)],
    )


def test_list_devices_is_empty_before_any_registration(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    assert registry.list_devices() == []


def test_get_returns_none_for_unknown_device(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    assert registry.get("unknown") is None


def test_register_inserts_and_get_returns_it(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    device = _device()
    registry.register(device)
    fetched = registry.get("dev_01")
    assert fetched is not None
    assert fetched.device_id == "dev_01"
    assert fetched.friendly_name == "workshop-node"
    assert fetched.platform == "linux"
    assert fetched.capabilities == [CapabilityRecord(name="diagnostics.echo", version=1)]
    assert registry.list_devices() == [fetched]


def test_register_fully_replaces_rather_than_merges(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.register(_device())
    replacement = DeviceRecord(
        device_id="dev_01",
        friendly_name="workshop-node",
        platform="linux",
        online=True,
        capabilities=[],  # full-set replacement (FR-8): capabilities dropped, not merged
    )
    registry.register(replacement)
    assert registry.get("dev_01").capabilities == []


def test_deregister_removes_the_entry_entirely(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.register(_device())
    registry.deregister("dev_01")
    assert registry.get("dev_01") is None
    assert registry.list_devices() == []


def test_deregister_unknown_device_is_a_silent_no_op(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.deregister("unknown")  # must not raise


def test_mark_offline_updates_last_seen_and_keeps_the_entry(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    device = DeviceRecord(
        device_id="dev_01",
        friendly_name="workshop-node",
        platform="linux",
        online=True,
        last_seen_at=1,  # deliberately stale — register() preserves a truthy caller-given value
        capabilities=[CapabilityRecord(name="diagnostics.echo", version=1)],
    )
    registry.register(device)
    assert registry.get("dev_01").last_seen_at == 1

    registry.mark_offline("dev_01")
    updated = registry.get("dev_01")
    assert updated is not None
    assert updated.last_seen_at > 1  # mark_offline's whole remaining job: stamp a real epoch-ms
    assert updated.capabilities == [CapabilityRecord(name="diagnostics.echo", version=1)]


def test_mark_offline_on_unknown_device_is_a_silent_no_op(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.mark_offline("unknown")  # must not raise
    assert registry.list_devices() == []


def test_device_survives_a_fresh_registry_instance_against_the_same_db(tmp_path):
    db_path = tmp_path / "registry.db"
    first = Registry(db_path)
    first.register(
        DeviceRecord(
            device_id="dev_1",
            friendly_name="n",
            platform="p",
            online=True,
            capabilities=[CapabilityRecord(name="diagnostics.echo", version=1)],
        )
    )

    second = Registry(db_path)  # simulates a daemon restart against the same file
    devices = second.list_devices()
    assert len(devices) == 1
    assert devices[0].device_id == "dev_1"
    assert devices[0].capabilities[0].name == "diagnostics.echo"
    # A restart re-reads from disk with a fresh in-memory `online` state — a device is not
    # "online" again until it reconnects and re-sends hello (§4.6's presence semantics), so a
    # freshly-restarted daemon reports it offline until then.
    assert devices[0].online is False


def test_registered_capability_input_schema_round_trips(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    schema = {"type": "object", "properties": {"payload": {"type": "object"}}}
    registry.register(
        DeviceRecord(
            device_id="dev_1",
            friendly_name="n",
            platform="p",
            online=True,
            capabilities=[
                CapabilityRecord(
                    name="diagnostics.echo", version=1, input_schema=schema, output_schema=schema
                )
            ],
        )
    )
    fetched = registry.get("dev_1")
    assert fetched.capabilities[0].input_schema == schema
    assert fetched.capabilities[0].output_schema == schema
