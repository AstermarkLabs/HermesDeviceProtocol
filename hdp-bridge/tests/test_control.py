"""`hdp_bridge.control` — the plugin↔bridge Unix-socket control plane.

`ctl_list_devices`/rejected-verb coverage (Task 5) sits above the fold, unchanged. Everything
below `ECHO_DESCRIPTOR` is Task 6: `ctl_invoke`'s ack-timeout/execution-deadline race, `ctl_cancel`,
`ctl_status`, and `ControlServer.close()` force-closing live connections.

`ctl_invoke` needs a real node on the other end of a real `NodeConnection` to exercise the ack/
result frames the race waits on — a fake "node" is a raw aiohttp WebSocket test client speaking
HDP/0 by hand, wired to the *same* `RegistryMem`/`InvocationsMem`/`connections`/`descriptors`
state as the `ControlServer` under test (mirrors `test_server.py`'s `_Harness`, and is a direct
port of the wire-level tests `hermes_device_plugin/tests/test_transport_embedded.py` used to carry
before that module's shared state moved into `hdp_bridge` — see that deleted file's git history
for the M1-era originals this section adapts).
"""

from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer
from hdp_bridge import config as bridge_config
from hdp_bridge import server as _server
from hdp_bridge.connection import NodeConnection
from hdp_bridge.control import ControlServer, read_frame, write_frame
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import RegistryMem
from hdp_bridge.types import DeviceRecord
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Hello, ResultMsg


@pytest.fixture
async def control_server(tmp_path):
    registry = RegistryMem()
    registry.register(DeviceRecord(device_id="dev_1", friendly_name="n", platform="p", online=True))
    invocations = InvocationsMem()
    socket_path = tmp_path / "bridge.sock"
    server = ControlServer(socket_path, registry=registry, invocations=invocations, connections={})
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


async def test_rejected_verb_gets_auth_failed(control_server):
    _server, socket_path = control_server
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    request = Envelope.new("ctl_policy_set", {})
    await write_frame(writer, request.to_wire())
    reply = Envelope.from_wire(await read_frame(reader))
    writer.close()
    assert reply.type == "error"
    assert reply.payload["code"] == "auth_failed"


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
    """One `RegistryMem`/`InvocationsMem`/`connections`/`descriptors` set, shared between the
    node-facing aiohttp app and the `ControlServer` under test — exactly the wiring
    `hdp_bridge.daemon.serve()` sets up in production, minus the real TCP bind."""

    def __init__(self, tmp_path) -> None:
        self.registry = RegistryMem()
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
        )

    def make_connection(self, ws: object) -> NodeConnection:
        return NodeConnection(
            ws,  # type: ignore[arg-type]
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


async def _connect_and_hello(client, *, device_name="test-node", capabilities=(ECHO_DESCRIPTOR,)):
    ws = await client.ws_connect("/hdp/v0/socket")
    hello = Hello(
        hdp_versions=(0,),
        device_name=device_name,
        capabilities=tuple(capabilities),
        credential=None,
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


async def test_ctl_invoke_round_trips_and_validates_output(node_client, ctl_conn):
    ws, device_id = await _connect_and_hello(node_client)
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


async def test_ctl_invoke_never_ack_yields_device_offline(node_client, ctl_conn, monkeypatch):
    monkeypatch.setattr(bridge_config, "ACK_TIMEOUT_S", 0.2)
    ws, device_id = await _connect_and_hello(node_client)
    reader, writer = ctl_conn

    reply = await _ctl_invoke(reader, writer, device_id=device_id)
    assert reply.payload["ok"] is False
    assert reply.payload["error"]["code"] == "device_offline"
    await ws.close()


async def test_ctl_invoke_slow_result_yields_invocation_timeout(node_client, ctl_conn):
    ws, device_id = await _connect_and_hello(node_client)
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


async def test_ctl_invoke_disconnect_mid_call_is_immediate(node_client, ctl_conn):
    ws, device_id = await _connect_and_hello(node_client)
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


async def test_ctl_invoke_malformed_result_is_rejected(node_client, ctl_conn):
    ws, device_id = await _connect_and_hello(node_client)
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


async def test_ctl_invoke_node_reported_failure_passes_through(node_client, ctl_conn):
    ws, device_id = await _connect_and_hello(node_client)
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
    ws, device_id = await _connect_and_hello(node_client)
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
    ws, device_id = await _connect_and_hello(node_client)
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


async def test_ctl_status_reports_connected_device_count(node_client, ctl_conn):
    _ws, _device_id = await _connect_and_hello(node_client)
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
    registry = RegistryMem()
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
