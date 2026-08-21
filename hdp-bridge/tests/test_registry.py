"""`Registry` in isolation — no server, no socket, no node. SQLite-backed (`store/db.py`); each
test gets its own `tmp_path`-scoped database file."""

from __future__ import annotations

import threading

import pytest
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


def test_register_uses_begin_immediate_for_atomic_full_set_replacement(tmp_path):
    """A deferred transaction can spend its busy timeout halfway into the replacement."""
    registry = Registry(tmp_path / "registry.db")
    statements = []
    registry._conn.set_trace_callback(statements.append)

    registry.register(_device())

    assert any(statement == "BEGIN IMMEDIATE" for statement in statements)


def test_registry_preserves_multiple_versions_of_one_capability(tmp_path):
    """Indexing descriptors by capability name alone silently drops a negotiated version."""
    registry = Registry(tmp_path / "registry.db")
    registry.register(
        DeviceRecord(
            device_id="dev_01",
            friendly_name="workshop-node",
            platform="linux",
            online=True,
            capabilities=[
                CapabilityRecord(name="diagnostics.echo", version=1),
                CapabilityRecord(name="diagnostics.echo", version=2),
            ],
        )
    )

    fetched = registry.get("dev_01")
    assert [(cap.name, cap.version) for cap in fetched.capabilities] == [
        ("diagnostics.echo", 1),
        ("diagnostics.echo", 2),
    ]


def test_register_serializes_full_set_before_opening_transaction(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.register(_device())
    statements = []
    registry._conn.set_trace_callback(statements.append)
    invalid_schema = {"not-json-serializable": object()}
    replacement = DeviceRecord(
        device_id="dev_01",
        friendly_name="replacement",
        platform="linux",
        online=True,
        capabilities=[
            CapabilityRecord(name="diagnostics.echo", version=2),
            CapabilityRecord(name="diagnostics.echo", version=3, input_schema=invalid_schema),
        ],
    )

    with pytest.raises(TypeError):
        registry.register(replacement)

    assert "BEGIN IMMEDIATE" not in statements
    current = registry.get("dev_01")
    assert current is not None
    assert current.friendly_name == "workshop-node"
    assert [(cap.name, cap.version) for cap in current.capabilities] == [("diagnostics.echo", 1)]


def test_register_replacement_is_scoped_to_one_device(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.register(_device("dev_a"))
    registry.register(_device("dev_b"))

    registry.register(
        DeviceRecord(
            device_id="dev_a",
            friendly_name="a",
            platform="linux",
            online=True,
            capabilities=[CapabilityRecord(name="notifications.send", version=1)],
        )
    )

    dev_a = registry.get("dev_a")
    dev_b = registry.get("dev_b")
    assert dev_a is not None and dev_b is not None
    assert [(cap.name, cap.version) for cap in dev_a.capabilities] == [("notifications.send", 1)]
    assert [(cap.name, cap.version) for cap in dev_b.capabilities] == [("diagnostics.echo", 1)]


def test_known_active_device_ids_excludes_every_non_active_state(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.register(_device("dev_active"))
    for device_id, state in (("dev_revoked", "revoked"), ("dev_pending", "pending")):
        device = _device(device_id)
        registry.register(
            DeviceRecord(
                device_id=device.device_id,
                friendly_name=device.friendly_name,
                platform=device.platform,
                online=True,
                state=state,
                capabilities=device.capabilities,
            )
        )

    assert registry.known_active_device_ids() == {"dev_active"}


def test_wal_reader_sees_complete_old_or_new_capability_set(tmp_path):
    db_path = tmp_path / "registry.db"
    Registry(db_path).register(_device())
    delete_reached = threading.Event()
    allow_commit = threading.Event()
    writer_errors = []

    def replace_capabilities() -> None:
        try:
            writer = Registry(db_path)

            def pause_after_delete() -> int:
                delete_reached.set()
                assert allow_commit.wait(timeout=2)
                return 0

            writer._conn.create_function("pause_after_delete", 0, pause_after_delete)
            writer._conn.execute(
                "CREATE TEMP TRIGGER pause_capability_swap AFTER DELETE ON capabilities "
                "BEGIN SELECT pause_after_delete(); END"
            )
            writer.register(
                DeviceRecord(
                    device_id="dev_01",
                    friendly_name="workshop-node",
                    platform="linux",
                    online=True,
                    capabilities=[
                        CapabilityRecord(name="diagnostics.echo", version=2),
                        CapabilityRecord(name="notifications.send", version=1),
                    ],
                )
            )
        except BaseException as exc:
            writer_errors.append(exc)

    thread = threading.Thread(target=replace_capabilities)
    thread.start()
    assert delete_reached.wait(timeout=2)
    reader = Registry(db_path)

    during = reader.get("dev_01")
    assert during is not None
    assert [(cap.name, cap.version) for cap in during.capabilities] == [("diagnostics.echo", 1)]

    allow_commit.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert writer_errors == []
    after = reader.get("dev_01")
    assert after is not None
    assert sorted((cap.name, cap.version) for cap in after.capabilities) == [
        ("diagnostics.echo", 2),
        ("notifications.send", 1),
    ]
