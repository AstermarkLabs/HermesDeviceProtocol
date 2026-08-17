"""Presence (FR-16) — heartbeat-driven `last_seen_at` and 45s dead-peer detection.

A `heartbeat` frame both replies in kind and persists `last_seen_at` to the registry DB. Absent
any heartbeat for `dead_peer_timeout_s`, `_dead_peer_monitor` closes the connection itself,
driving the existing `_on_disconnect` -> `fail_all_for_device` path (same as any ordinary socket
drop) — it must NOT set `_disconnect_reason` to anything other than its default
`"device_offline"`; that value is reserved for operator revocation (Task 13)."""

from __future__ import annotations

import asyncio

from hdp_bridge.connection import NodeConnection
from hdp_bridge.invocations import DeviceDisconnected, InvocationsMem
from hdp_bridge.registry import Registry
from hdp_bridge.store import db


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_str(self, data):
        self.sent.append(data)

    async def close(self, *, code, message=b""):
        self.closed_with = code


async def test_heartbeat_updates_last_seen_at(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    registry = Registry(db_path)
    connection = NodeConnection(
        _FakeWS(),
        conn=conn,
        registry=registry,
        invocations=InvocationsMem(),
        connections={},
        descriptors={},
    )
    connection.device_id = "dev_1"
    import json

    from hdp_proto.envelope import Envelope

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
    invocation_id, entry = invocations.mint_for("dev_1")

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
    invocation_id, entry = invocations.mint_for("dev_1")

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
