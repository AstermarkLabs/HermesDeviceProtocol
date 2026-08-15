"""`RegistryMem` in isolation — no server, no socket, no node."""

from __future__ import annotations

from hdp_bridge.registry import RegistryMem
from hdp_bridge.types import CapabilityRecord, DeviceRecord


def _device(device_id: str = "dev_01", *, online: bool = True) -> DeviceRecord:
    return DeviceRecord(
        device_id=device_id,
        friendly_name="workshop-node",
        platform="linux",
        online=online,
        capabilities=[CapabilityRecord(name="diagnostics.echo", version=1)],
    )


def test_list_devices_is_empty_before_any_registration():
    registry = RegistryMem()
    assert registry.list_devices() == []


def test_get_returns_none_for_unknown_device():
    registry = RegistryMem()
    assert registry.get("unknown") is None


def test_register_inserts_and_get_returns_it():
    registry = RegistryMem()
    device = _device()
    registry.register(device)
    assert registry.get("dev_01") is device
    assert registry.list_devices() == [device]


def test_register_fully_replaces_rather_than_merges():
    registry = RegistryMem()
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


def test_deregister_removes_the_entry_entirely():
    registry = RegistryMem()
    registry.register(_device())
    registry.deregister("dev_01")
    assert registry.get("dev_01") is None
    assert registry.list_devices() == []


def test_deregister_unknown_device_is_a_silent_no_op():
    registry = RegistryMem()
    registry.deregister("unknown")  # must not raise


def test_mark_offline_flips_online_and_keeps_the_entry():
    registry = RegistryMem()
    registry.register(_device())
    registry.mark_offline("dev_01")
    device = registry.get("dev_01")
    assert device is not None
    assert device.online is False
    assert device.capabilities == [CapabilityRecord(name="diagnostics.echo", version=1)]


def test_mark_offline_on_unknown_device_is_a_silent_no_op():
    registry = RegistryMem()
    registry.mark_offline("unknown")  # must not raise
    assert registry.list_devices() == []


def test_mark_offline_is_idempotent_for_an_already_offline_device():
    registry = RegistryMem()
    registry.register(_device(online=False))
    before = registry.get("dev_01")
    registry.mark_offline("dev_01")
    after = registry.get("dev_01")
    assert after is before  # unchanged: already offline, so no replacement happens
