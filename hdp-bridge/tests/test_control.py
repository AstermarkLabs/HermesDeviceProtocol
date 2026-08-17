"""`hdp_bridge.control` — the plugin↔bridge Unix-socket control plane.

`ctl_list_devices`/rejected-verb coverage (Task 5) sits above the fold, unchanged. Everything
below `ECHO_DESCRIPTOR` is Task 6: `ctl_invoke`'s ack-timeout/execution-deadline race, `ctl_cancel`,
`ctl_status`, and `ControlServer.close()` force-closing live connections.

`ctl_invoke` needs a real node on the other end of a real `NodeConnection` to exercise the ack/
result frames the race waits on — a fake "node" is a raw aiohttp WebSocket test client speaking
HDP/0 by hand, wired to the *same* `Registry`/`InvocationsMem`/`connections`/`descriptors`
state as the `ControlServer` under test (mirrors `test_server.py`'s `_Harness`, and is a direct
port of the wire-level tests `hermes_device_plugin/tests/test_transport_embedded.py` used to carry
before that module's shared state moved into `hdp_bridge` — see that deleted file's git history
for the M1-era originals this section adapts).
"""

from __future__ import annotations

import asyncio
import json
import socket

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer
from hdp_bridge import config as bridge_config
from hdp_bridge import pairing
from hdp_bridge import server as _server
from hdp_bridge.audit import AuditWriter
from hdp_bridge.connection import NodeConnection
from hdp_bridge.control import ControlServer, read_frame, write_frame
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import Registry
from hdp_bridge.store import db
from hdp_bridge.types import DeviceRecord
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Hello, ResultMsg


@pytest.fixture
async def control_server(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    registry.register(DeviceRecord(device_id="dev_1", friendly_name="n", platform="p", online=True))
    invocations = InvocationsMem()
    socket_path = tmp_path / "bridge.sock"
    audit = AuditWriter(tmp_path / "audit")
    server = ControlServer(
        socket_path, registry=registry, invocations=invocations, connections={}, audit=audit
    )
    await server.start()
    yield server, socket_path
    await server.close()


async def test_ctl_list_devices_returns_registered_devices(control_server):
    _server, socket_path = control_server
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    request = Envelope.new("ctl_list_devices", {})
    await write_frame(writer, request.to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    writer.close()
    assert reply.type == "ctl_list_devices_reply"
    assert reply.payload["devices"][0]["device_id"] == "dev_1"


async def test_ctl_devices_list_detailed_is_an_alias_of_ctl_list_devices(control_server):
    """Task 17 Step 2: `DeviceRecord.to_wire()` (Task 2) already carries `state`/
    `first_paired_at`/`last_seen_at`, so `ctl_devices_list_detailed` is a genuine alias — same
    payload as `ctl_list_devices`, just its own pinned wire type (`ctl_devices_list_detailed_reply`,
    `KNOWN_TYPES`) rather than a second code path."""
    server, socket_path = control_server
    server._registry.register(
        DeviceRecord(
            device_id="dev_2",
            friendly_name="detailed",
            platform="p",
            online=False,
            state="active",
            first_paired_at=1000,
            last_seen_at=2000,
        )
    )
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    request = Envelope.new("ctl_devices_list_detailed", {})
    await write_frame(writer, request.to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    writer.close()

    assert reply.type == "ctl_devices_list_detailed_reply"
    by_id = {d["device_id"]: d for d in reply.payload["devices"]}
    assert by_id["dev_2"]["state"] == "active"
    assert by_id["dev_2"]["first_paired_at"] == 1000
    assert by_id["dev_2"]["last_seen_at"] == 2000


async def test_ctl_audit_tail_returns_todays_records(control_server, tmp_path):
    server, socket_path = control_server
    server._audit.record("daemon_start")
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    request = Envelope.new("ctl_audit_tail", {})
    await write_frame(writer, request.to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    writer.close()

    assert reply.type == "ctl_audit_tail_reply"
    events = [line["event"] for line in reply.payload["lines"]]
    assert events == ["daemon_start"]


async def test_ctl_audit_tail_with_no_audit_writer_returns_empty(tmp_path):
    registry = Registry(tmp_path / "registry.db")
    invocations = InvocationsMem()
    socket_path = tmp_path / "bridge_no_audit.sock"
    server = ControlServer(socket_path, registry=registry, invocations=invocations, connections={})
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        request = Envelope.new("ctl_audit_tail", {})
        await write_frame(writer, request.to_wire())
        reply = Envelope.from_wire(await read_frame(reader))
        writer.close()
        assert reply.type == "ctl_audit_tail_reply"
        assert reply.payload["lines"] == []
    finally:
        await server.close()


async def test_rejected_verb_gets_auth_failed(control_server, tmp_path):
    _server, socket_path = control_server
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    request = Envelope.new("ctl_policy_set", {})
    await write_frame(writer, request.to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    writer.close()
    assert reply.type == "error"
    assert reply.payload["code"] == "auth_failed"

    audit_files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "rejected_control_verb"
    assert record["verb"] == "ctl_policy_set"


# -- ctl_invoke / ctl_cancel / ctl_status ------------------------------------------------------

ECHO_DESCRIPTOR = CapabilityDescriptor(
    name="diagnostics.echo",
    version=1,
    input_schema={
        "type": "object",
        "properties": {"payload": {"type": "object"}},
        "required": ["payload"],
    },
    output_schema={
        "type": "object",
        "properties": {"payload": {"type": "object"}},
        "required": ["payload"],
    },
)


class _Harness:
    """One `Registry`/`InvocationsMem`/`connections`/`descriptors` set, shared between the
    node-facing aiohttp app and the `ControlServer` under test — exactly the wiring
    `hdp_bridge.daemon.serve()` sets up in production, minus the real TCP bind."""

    def __init__(self, tmp_path) -> None:
        db_path = tmp_path / "registry.db"
        self.conn = db.connect(db_path)
        self.registry = Registry(db_path)
        self.invocations = InvocationsMem()
        self.connections: dict[str, NodeConnection] = {}
        self.descriptors: dict = {}
        self.socket_path = tmp_path / "bridge.sock"
        self.control = ControlServer(
            self.socket_path,
            registry=self.registry,
            invocations=self.invocations,
            connections=self.connections,
            descriptors=self.descriptors,
            conn=self.conn,
        )

    def make_connection(self, ws: object) -> NodeConnection:
        return NodeConnection(
            ws,  # type: ignore[arg-type]
            conn=self.conn,
            registry=self.registry,
            invocations=self.invocations,
            connections=self.connections,
            descriptors=self.descriptors,
        )


@pytest.fixture
async def harness(tmp_path):
    h = _Harness(tmp_path)
    await h.control.start()
    yield h
    await h.control.close()


@pytest.fixture
async def node_client(harness):
    app = _server.build_app(harness.make_connection)
    async with TestClient(TestServer(app)) as c:
        yield c


@pytest.fixture
async def ctl_conn(harness):
    reader, writer = await asyncio.open_unix_connection(str(harness.socket_path))
    yield reader, writer
    writer.close()


async def _connect_and_hello(
    client, harness, *, device_name="test-node", capabilities=(ECHO_DESCRIPTOR,)
):
    ws = await client.ws_connect("/hdp/v0/socket")
    code = pairing.mint_pairing_code(harness.conn)
    hello = Hello(
        hdp_versions=(0,),
        device_name=device_name,
        capabilities=tuple(capabilities),
        credential=f"pair:{code}",
    )
    envelope = Envelope.new("hello", hello.to_wire())
    await ws.send_str(json.dumps(envelope.to_wire()))
    msg = await ws.receive(timeout=5)
    welcome_envelope = Envelope.from_wire(json.loads(msg.data))
    assert welcome_envelope.type == "welcome"
    return ws, welcome_envelope.payload["device_id"]


async def _ctl_invoke(
    reader, writer, *, device_id, deadline_ms=2000, capability="diagnostics.echo"
):
    request = Envelope.new(
        "ctl_invoke",
        {
            "device_id": device_id,
            "capability": capability,
            "version": 1,
            "args": {"payload": {}},
            "deadline_ms": deadline_ms,
        },
    )
    await write_frame(writer, request.to_wire())
    return Envelope.from_wire(await read_frame(reader))


async def test_ctl_invoke_against_unknown_device_is_device_offline(ctl_conn):
    reader, writer = ctl_conn
    reply = await _ctl_invoke(reader, writer, device_id="dev_nonexistent")
    assert reply.type == "ctl_invoke_reply"
    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "device_offline"


async def test_ctl_invoke_round_trips_and_validates_output(node_client, ctl_conn, harness):
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    async def _serve_one():
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        assert envelope.type == "invoke"
        invocation_id = envelope.corr
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=invocation_id).to_wire()))
        result = ResultMsg(ok=True, data={"payload": {"x": 1}}, error=None)
        result_envelope = Envelope.new("result", result.to_wire(), corr=invocation_id)
        await ws.send_str(json.dumps(result_envelope.to_wire()))

    server_task = asyncio.create_task(_serve_one())
    reply = await _ctl_invoke(reader, writer, device_id=device_id)
    await server_task

    assert reply.payload["ok"] is True
    assert reply.payload["data"] == {"payload": {"x": 1}}
    assert reply.payload["invocation_id"]
    await ws.close()


async def test_ctl_invoke_never_ack_yields_device_offline(
    node_client, ctl_conn, monkeypatch, harness
):
    monkeypatch.setattr(bridge_config, "ACK_TIMEOUT_S", 0.2)
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    reply = await _ctl_invoke(reader, writer, device_id=device_id)
    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "device_offline"
    await ws.close()


async def test_ctl_invoke_slow_result_yields_invocation_timeout(node_client, ctl_conn, harness):
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    async def _ack_and_never_answer():
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=envelope.corr).to_wire()))

    server_task = asyncio.create_task(_ack_and_never_answer())
    reply = await _ctl_invoke(reader, writer, device_id=device_id, deadline_ms=200)
    await server_task

    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "invocation_timeout"
    await ws.close()


async def test_ctl_invoke_disconnect_mid_call_is_immediate(node_client, ctl_conn, harness):
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    async def _drop_connection():
        await ws.receive(timeout=5)  # the invoke frame
        await ws.close()

    server_task = asyncio.create_task(_drop_connection())
    loop = asyncio.get_running_loop()
    start = loop.time()
    reply = await _ctl_invoke(reader, writer, device_id=device_id, deadline_ms=30_000)
    elapsed = loop.time() - start
    await server_task

    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "device_offline"
    assert elapsed < 5.0  # nowhere near the 30s deadline


async def test_ctl_invoke_malformed_result_is_rejected(node_client, ctl_conn, harness):
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    async def _reply_with_wrong_shape():
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        invocation_id = envelope.corr
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=invocation_id).to_wire()))
        # `diagnostics.echo@1`'s output schema requires a `payload` field — omit it.
        bad_result = ResultMsg(ok=True, data={"not_payload": 1}, error=None)
        result_envelope = Envelope.new("result", bad_result.to_wire(), corr=invocation_id)
        await ws.send_str(json.dumps(result_envelope.to_wire()))

    server_task = asyncio.create_task(_reply_with_wrong_shape())
    reply = await _ctl_invoke(reader, writer, device_id=device_id)
    await server_task

    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "malformed_result"
    await ws.close()


async def test_ctl_invoke_node_reported_failure_passes_through(node_client, ctl_conn, harness):
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    async def _reply_with_failure():
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        invocation_id = envelope.corr
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=invocation_id).to_wire()))
        result = ResultMsg(
            ok=False,
            data=None,
            error={"code": "capability_unsupported", "message": "m", "hint": "h"},
        )
        result_envelope = Envelope.new("result", result.to_wire(), corr=invocation_id)
        await ws.send_str(json.dumps(result_envelope.to_wire()))

    server_task = asyncio.create_task(_reply_with_failure())
    reply = await _ctl_invoke(reader, writer, device_id=device_id)
    await server_task

    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "capability_unsupported"
    await ws.close()


async def test_ctl_invoke_expired_invocation_leaves_nothing_pending(
    node_client, ctl_conn, monkeypatch, harness
):
    """Nothing-leaks invariant (hdp-spec/HDP-0.md §7): after a terminal outcome — here, an
    ack timeout — the invocation_id is absent from the pending table (FR-30's ordering rule:
    `expire()` runs before the best-effort `cancel` is sent)."""
    monkeypatch.setattr(bridge_config, "ACK_TIMEOUT_S", 0.2)
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    async def _never_ack():
        await ws.receive(timeout=5)  # the invoke frame; do nothing with it

    server_task = asyncio.create_task(_never_ack())
    reply = await _ctl_invoke(reader, writer, device_id=device_id)
    await server_task

    assert reply.payload["error"]["code"] == "device_offline"
    assert harness.invocations.is_pending(reply.payload["invocation_id"]) is False
    await ws.close()


async def test_ctl_cancel_on_pending_invocation_resolves_it_negatively(
    node_client, ctl_conn, harness
):
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    invoke_reply_task = asyncio.create_task(
        _ctl_invoke(reader, writer, device_id=device_id, deadline_ms=30_000)
    )

    # Let the invoke land, ack it so `mint_for`'s entry is visible, then cancel out-of-band on a
    # second control connection while the first is still awaiting its reply.
    msg = await ws.receive(timeout=5)
    envelope = Envelope.from_wire(json.loads(msg.data))
    invocation_id = envelope.corr
    await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=invocation_id).to_wire()))
    await asyncio.sleep(0.05)  # let the ack be processed before we cancel

    cancel_reader, cancel_writer = await asyncio.open_unix_connection(str(harness.socket_path))
    await write_frame(
        cancel_writer,
        Envelope.new("ctl_cancel", {"invocation_id": invocation_id, "reason": "test"}).to_wire(),
    )
    cancel_reply = Envelope.from_wire(await read_frame(cancel_reader))
    cancel_writer.close()
    assert cancel_reply.type == "ctl_cancel_reply"
    assert cancel_reply.payload["ok"] is True

    reply = await invoke_reply_task
    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "bridge_unavailable"
    assert harness.invocations.is_pending(invocation_id) is False
    await ws.close()


async def test_ctl_cancel_on_unknown_invocation_is_a_silent_no_op(ctl_conn):
    reader, writer = ctl_conn
    await write_frame(
        writer,
        Envelope.new("ctl_cancel", {"invocation_id": "inv_nonexistent", "reason": "x"}).to_wire(),
    )
    reply = Envelope.from_wire(await read_frame(reader))
    assert reply.type == "ctl_cancel_reply"
    assert reply.payload["ok"] is True


async def test_ctl_status_reports_connected_device_count(node_client, ctl_conn, harness):
    _ws, _device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn
    await write_frame(writer, Envelope.new("ctl_status", {}).to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    assert reply.type == "ctl_status_reply"
    assert reply.payload["healthy"] is True
    assert reply.payload["detail"] == "1 device(s) connected"


async def test_ctl_list_approvals_verb_is_not_implemented_yet(ctl_conn):
    """M3 adds the handler and the client call together (this task deliberately does not)."""
    reader, writer = ctl_conn
    await write_frame(writer, Envelope.new("ctl_list_approvals", {}).to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    assert reply.type == "error"
    assert reply.payload["code"] == "not_implemented"


async def test_close_force_closes_live_connections(tmp_path):
    """`Server.close()` alone leaves already-accepted connections open — without this, a stopped
    daemon would leak every open plugin connection instead of actually disconnecting it."""
    registry = Registry(tmp_path / "registry.db")
    invocations = InvocationsMem()
    socket_path = tmp_path / "bridge.sock"
    server = ControlServer(socket_path, registry=registry, invocations=invocations, connections={})
    await server.start()

    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    await write_frame(writer, Envelope.new("ctl_list_devices", {}).to_wire())
    await read_frame(reader)  # prove the connection is alive before closing

    await server.close()

    # The server-side writer was force-closed; the client's next read sees EOF, not a hang.
    with pytest.raises((asyncio.IncompleteReadError, ConnectionResetError)):
        await asyncio.wait_for(read_frame(reader), timeout=2.0)
    writer.close()


async def test_ctl_devices_revoke_disconnects_live_node_and_fails_in_flight_invoke(
    node_client, ctl_conn, harness
):
    """End-to-end (Task 13, FR-15): a live node connection receives a `revoke` frame and its
    socket is closed, and any invocation still awaited via a second control connection comes back
    `revoked`, not `device_offline`."""
    ws, device_id = await _connect_and_hello(node_client, harness)
    reader, writer = ctl_conn

    invoke_reply_task = asyncio.create_task(
        _ctl_invoke(reader, writer, device_id=device_id, deadline_ms=30_000)
    )
    await ws.receive(timeout=5)  # the invoke frame — deliberately never acked

    revoke_reader, revoke_writer = await asyncio.open_unix_connection(str(harness.socket_path))
    await write_frame(
        revoke_writer, Envelope.new("ctl_devices_revoke", {"device_id": device_id}).to_wire()
    )
    revoke_reply = Envelope.from_wire(await read_frame(revoke_reader))
    revoke_writer.close()
    assert revoke_reply.type == "ctl_devices_revoke_reply"
    assert revoke_reply.payload["ok"] is True

    reply = await invoke_reply_task
    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "revoked"

    # The node received the `revoke` frame (step 2), then its socket was actually closed
    # server-side (step 3 of the four-step order).
    revoke_frame_msg = await ws.receive(timeout=5)
    assert revoke_frame_msg.type == WSMsgType.TEXT
    assert json.loads(revoke_frame_msg.data)["type"] == "revoke"
    close_msg = await ws.receive(timeout=5)
    assert close_msg.type == WSMsgType.CLOSE


async def test_ctl_devices_revoke_without_device_id_is_no_matching_device(ctl_conn):
    reader, writer = ctl_conn
    await write_frame(writer, Envelope.new("ctl_devices_revoke", {}).to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    assert reply.type == "error"
    assert reply.payload["code"] == "no_matching_device"


async def test_ctl_devices_revoke_of_an_unknown_device_is_an_error_not_a_success_reply(ctl_conn):
    """Finding I4: `revoke_credential` used to return `None`, so a revoke that matched zero rows
    was indistinguishable from one that matched. It now reports its rowcount up through
    `revocation.revoke_device`, and zero becomes an `error` envelope — which is what lets the
    operator CLIs stop fail-open-reporting "revoked <id>" for a device that was never paired."""
    reader, writer = ctl_conn
    await write_frame(
        writer, Envelope.new("ctl_devices_revoke", {"device_id": "dev_never_paired"}).to_wire()
    )
    reply = Envelope.from_wire(await read_frame(reader))
    assert reply.type == "error"
    assert reply.payload["code"] == "no_matching_device"


async def test_close_drains_a_connection_still_in_the_kernel_accept_backlog(tmp_path):
    """Isolates the exact race `ControlServer.close()`'s backlog-drain step exists for: a client
    whose `connect()` already completed at the OS level (queued in the listening socket's kernel
    accept backlog) but which asyncio has not yet called `accept()` on — because nothing has ever
    given the event loop a chance to run its accept callback for this connection — must not
    survive `close()` un-force-closed. `test_close_force_closes_live_connections` above only
    covers a connection that's already fully wired up (round-tripped a request even) well before
    `close()` runs; it can't exercise this narrower, tighter window at all.

    Connecting with a raw, plain `socket.socket(...).connect(...)` — never `await`ing anything, so
    the event loop gets zero opportunity to run between the connect and `close()` — is what makes
    this deterministic instead of a probabilistic race depending on how many event-loop ticks
    asyncio's own accept pipeline happens to take: the connection is *guaranteed* to still be
    sitting un-accepted in the kernel backlog when `close()` runs, every single time this test
    runs, on any platform, under any scheduler load. `raw.connect()` itself is a plain local-socket
    syscall for `AF_UNIX` (no network handshake), so it returns immediately regardless."""
    registry = Registry(tmp_path / "registry.db")
    invocations = InvocationsMem()
    socket_path = tmp_path / "bridge.sock"
    server = ControlServer(socket_path, registry=registry, invocations=invocations, connections={})
    await server.start()

    raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    raw.connect(str(socket_path))
    try:
        # No `await` between the connect above and `close()` below: the event loop has not run a
        # single iteration since the OS accepted this connection into the backlog, so asyncio's
        # own accept callback for the listening socket has had no opportunity to fire.
        await server.close()

        # If this connection had slipped through un-force-closed (the bug the backlog drain
        # fixes), the peer socket would still look "connected" from the OS's point of view and
        # this read would hang until the 2s timeout instead of observing a clean, immediate EOF.
        raw.settimeout(2.0)
        data = raw.recv(4096)
        assert data == b""
    finally:
        raw.close()
