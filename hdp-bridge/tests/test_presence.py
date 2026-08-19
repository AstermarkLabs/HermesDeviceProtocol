"""Presence (FR-16) — heartbeat-driven `last_seen_at` and 45s dead-peer detection.

A `heartbeat` frame both replies in kind and persists `last_seen_at` to the registry DB. Absent
any heartbeat for `dead_peer_timeout_s`, `_dead_peer_monitor` closes the connection itself,
driving the existing `_on_disconnect` -> `fail_all_for_device` path (same as any ordinary socket
drop) — it must NOT set `_disconnect_reason` to anything other than its default
`"device_offline"`; that value is reserved for operator revocation (Task 13)."""

from __future__ import annotations

import asyncio
import json

import pytest
from hdp_bridge.connection import NodeConnection
from hdp_bridge.invocations import DeviceDisconnected, InvocationsMem
from hdp_bridge.registry import Registry
from hdp_bridge.store import db
from hdp_bridge.types import CapabilityRecord, DeviceRecord
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope
from hdp_proto.messages import CapabilitiesMsg


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_str(self, data):
        self.sent.append(data)

    async def close(self, *, code, message=b""):
        self.closed_with = code


def _echo_descriptor(version: int) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name="diagnostics.echo",
        version=version,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )


async def test_heartbeat_updates_last_seen_at(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    registry = Registry(db_path)
    connections = {}
    connection = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=registry,
        invocations=InvocationsMem(),
        connections=connections,
        descriptors={},
    )
    connection.device_id = "dev_1"
    connections["dev_1"] = connection

    await connection._handle_frame(json.dumps(Envelope.new("heartbeat", {}).to_wire()))
    row = conn.execute("SELECT last_seen_at FROM devices WHERE device_id = 'dev_1'").fetchone()
    assert row[0] > 0


async def test_dead_peer_after_45s_of_silence_closes_and_fails_in_flight(tmp_path, monkeypatch):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    registry = Registry(db_path)
    invocations = InvocationsMem()
    ws = _FakeWS()
    connection = NodeConnection(
        ws,
        conn=conn,
        registry=registry,
        invocations=invocations,
        connections={},
        descriptors={},
        dead_peer_timeout_s=0.2,  # test-only override, see Step 2
    )
    connection.device_id = "dev_1"
    connections = {"dev_1": connection}
    connection._connections = connections
    invocation_id, entry = invocations.mint_for("dev_1", connection=connection)

    monitor_task = asyncio.create_task(connection._dead_peer_monitor())
    await asyncio.sleep(0.4)
    monitor_task.cancel()

    assert ws.closed_with is not None
    assert entry.ack_future.done()
    # Retrieve the exception too, not just check `.done()` — an unretrieved exception on a
    # completed future logs "Future exception was never retrieved" noise at GC (Task 13's exact
    # failure mode), and this doubles as coverage that the *reason* is right.
    try:
        entry.ack_future.result()
        raised = None
    except DeviceDisconnected as exc:
        raised = exc
    assert raised is not None
    assert raised.reason == "device_offline"


async def test_dead_peer_timeout_leaves_disconnect_reason_at_default(tmp_path):
    """The dead-peer monitor drives an ordinary disconnect, not a revocation. Asserting on
    `connection._disconnect_reason` directly would pass vacuously (nothing ever writes to it on
    this path in a correct implementation OR a broken one that forgets to fail invocations at
    all) — the assertion that actually catches a regression setting `"revoked"`/anything else is
    reading the reason back off the *failed future* that `fail_all_for_device` populates."""
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    registry = Registry(db_path)
    invocations = InvocationsMem()
    ws = _FakeWS()
    connection = NodeConnection(
        ws,
        conn=conn,
        registry=registry,
        invocations=invocations,
        connections={},
        descriptors={},
        dead_peer_timeout_s=0.2,
    )
    connection.device_id = "dev_1"
    connection._connections = {"dev_1": connection}
    invocation_id, entry = invocations.mint_for("dev_1", connection=connection)

    monitor_task = asyncio.create_task(connection._dead_peer_monitor())
    await asyncio.sleep(0.4)
    monitor_task.cancel()

    assert connection._disconnect_reason == "device_offline"
    try:
        await entry.ack_future
        raised = None
    except DeviceDisconnected as exc:
        raised = exc
    assert raised is not None
    assert raised.reason == "device_offline"


async def test_stale_disconnect_does_not_remove_replacement_or_fail_its_calls(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    registry = Registry(db_path)
    invocations = InvocationsMem()
    connections = {}
    old = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=registry,
        invocations=invocations,
        connections=connections,
        descriptors={},
    )
    replacement = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=registry,
        invocations=invocations,
        connections=connections,
        descriptors={},
    )
    old.device_id = replacement.device_id = "dev_1"
    connections["dev_1"] = replacement
    old_id, old_entry = invocations.mint_for("dev_1", connection=old)
    new_id, new_entry = invocations.mint_for("dev_1", connection=replacement)

    await old._on_disconnect()

    assert connections["dev_1"] is replacement
    assert not invocations.is_pending(old_id)
    with pytest.raises(DeviceDisconnected):
        await old_entry.ack_future
    assert invocations.is_pending(new_id)
    assert not new_entry.ack_future.done()


@pytest.mark.parametrize("stale_capabilities", [(), (_echo_descriptor(2),)])
async def test_stale_generation_cannot_replace_current_capabilities(tmp_path, stale_capabilities):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    registry = Registry(db_path)
    current = _echo_descriptor(1)
    registry.register(
        DeviceRecord(
            device_id="dev_1",
            friendly_name="replacement",
            platform="linux",
            online=True,
            capabilities=[
                CapabilityRecord(
                    name=current.name,
                    version=current.version,
                    input_schema=current.input_schema,
                    output_schema=current.output_schema,
                )
            ],
        )
    )
    connections = {}
    descriptors = {"dev_1": {(current.name, current.version): current}}
    old = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=registry,
        invocations=InvocationsMem(),
        connections=connections,
        descriptors=descriptors,
    )
    replacement = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=registry,
        invocations=InvocationsMem(),
        connections=connections,
        descriptors=descriptors,
    )
    old.device_id = replacement.device_id = "dev_1"
    connections["dev_1"] = replacement
    message = CapabilitiesMsg(capabilities=stale_capabilities)

    await old._handle_frame(json.dumps(Envelope.new("capabilities", message.to_wire()).to_wire()))

    assert [(cap.name, cap.version) for cap in registry.get("dev_1").capabilities] == [
        ("diagnostics.echo", 1)
    ]
    assert list(descriptors["dev_1"]) == [("diagnostics.echo", 1)]


async def test_stale_generation_heartbeat_cannot_update_current_presence(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 123, 'active')"
    )
    connections = {}
    old = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=Registry(db_path),
        invocations=InvocationsMem(),
        connections=connections,
        descriptors={},
    )
    replacement = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=Registry(db_path),
        invocations=InvocationsMem(),
        connections=connections,
        descriptors={},
    )
    old.device_id = replacement.device_id = "dev_1"
    connections["dev_1"] = replacement

    await old._handle_frame(json.dumps(Envelope.new("heartbeat", {}).to_wire()))

    row = conn.execute("SELECT last_seen_at FROM devices WHERE device_id = 'dev_1'").fetchone()
    assert row[0] == 123
