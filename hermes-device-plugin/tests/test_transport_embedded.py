"""Direct wire-level tests for `EmbeddedTransport` — a fake "node" is a raw aiohttp WebSocket
test client speaking HDP/0 by hand, not the real reference node (that's `hdp-reference-node`,
exercised end to end by `tests/conformance/`). These tests exist to catch wire-shape bugs close
to the code that produces them, before the reference node and conformance suite exist.

Uses `aiohttp.test_utils` directly against `_server.build_app(...)` — bypassing
`EmbeddedServer`'s real `AppRunner`/`TCPSite` bind (and therefore `$HERMES_HOME`) entirely, since
these tests only need the `Application`'s routing/dispatch, not a real bound socket.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Hello, ResultMsg
from hermes_device_plugin.transport import _server
from hermes_device_plugin.transport.base import InvokeRequest
from hermes_device_plugin.transport.embedded import EmbeddedTransport

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


@pytest.fixture
def transport():
    return EmbeddedTransport()


@pytest.fixture
async def client(transport):
    app = _server.build_app(transport._make_connection)
    async with TestClient(TestServer(app)) as c:
        yield c


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
    device_id = welcome_envelope.payload["device_id"]
    return ws, device_id


async def test_health_endpoint_is_live(client):
    resp = await client.get("/hdp/v0/health")
    assert resp.status == 200
    assert await resp.json() == {"status": "ok"}


async def test_blobs_route_is_reserved(client):
    resp = await client.get("/hdp/v0/blobs")
    assert resp.status == 501


async def test_pair_route_is_absent_at_m1(client):
    resp = await client.post("/hdp/v0/pair")
    assert resp.status == 404


async def test_hello_welcome_handshake_registers_the_device(client, transport):
    ws, device_id = await _connect_and_hello(client)
    devices = await transport.list_devices()
    assert len(devices) == 1
    assert devices[0].device_id == device_id
    assert devices[0].online is True
    assert devices[0].capabilities[0].name == "diagnostics.echo"
    await ws.close()


async def test_version_mismatch_closes_before_any_reply(client):
    ws = await client.ws_connect("/hdp/v0/socket")
    await ws.send_str(
        json.dumps({"hdp": "99", "type": "hello", "id": "x", "ts": 0, "corr": None, "payload": {}})
    )
    msg = await ws.receive(timeout=5)
    # No `error` envelope — the connection just closes.
    assert msg.type.name == "CLOSE" or ws.closed


async def test_malformed_frame_gets_an_error_reply_and_stays_open(client):
    ws = await client.ws_connect("/hdp/v0/socket")
    await ws.send_str("not json at all")
    msg = await ws.receive(timeout=5)
    envelope = Envelope.from_wire(json.loads(msg.data))
    assert envelope.type == "error"
    assert not ws.closed
    await ws.close()


async def test_invoke_ack_result_round_trips_and_validates_output(client, transport):
    ws, device_id = await _connect_and_hello(client)

    async def _serve_one():
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        assert envelope.type == "invoke"
        invocation_id = envelope.corr
        ack = Envelope.new("ack", {}, corr=invocation_id)
        await ws.send_str(json.dumps(ack.to_wire()))
        result = ResultMsg(ok=True, data={"payload": {"x": 1}}, error=None)
        result_envelope = Envelope.new("result", result.to_wire(), corr=invocation_id)
        await ws.send_str(json.dumps(result_envelope.to_wire()))

    server_task = asyncio.create_task(_serve_one())
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {"x": 1}},
        deadline_ms=2000,
    )
    result = await transport.invoke(req)
    await server_task

    assert result.ok is True
    assert result.data == {"payload": {"x": 1}}
    await ws.close()


async def test_never_ack_yields_device_offline(client, transport, monkeypatch):
    from hermes_device_plugin import config

    monkeypatch.setattr(config, "ACK_TIMEOUT_S", 0.2)
    ws, device_id = await _connect_and_hello(client)
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {}},
        deadline_ms=2000,
    )
    result = await transport.invoke(req)
    assert result.ok is False
    assert result.error["code"] == "device_offline"
    await ws.close()


async def test_slow_result_yields_invocation_timeout(client, transport):
    ws, device_id = await _connect_and_hello(client)

    async def _ack_and_never_answer():
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        ack = Envelope.new("ack", {}, corr=envelope.corr)
        await ws.send_str(json.dumps(ack.to_wire()))

    server_task = asyncio.create_task(_ack_and_never_answer())
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {}},
        deadline_ms=200,
    )
    result = await transport.invoke(req)
    await server_task

    assert result.ok is False
    assert result.error["code"] == "invocation_timeout"
    await ws.close()


async def test_disconnect_mid_call_is_immediate_not_deferred_to_deadline(client, transport):
    ws, device_id = await _connect_and_hello(client)

    async def _drop_connection():
        await ws.receive(timeout=5)  # the invoke frame
        await ws.close()

    server_task = asyncio.create_task(_drop_connection())
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {}},
        deadline_ms=30_000,  # deliberately long — the point is we don't wait for it
    )
    loop = asyncio.get_running_loop()
    start = loop.time()
    result = await transport.invoke(req)
    elapsed = loop.time() - start
    await server_task

    assert result.ok is False
    assert result.error["code"] == "device_offline"
    assert elapsed < 5.0  # nowhere near the 30s deadline


async def test_malformed_result_is_rejected_and_never_reaches_the_model(client, transport):
    ws, device_id = await _connect_and_hello(client)

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
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {}},
        deadline_ms=2000,
    )
    result = await transport.invoke(req)
    await server_task

    assert result.ok is False
    assert result.error["code"] == "malformed_result"
    await ws.close()


async def test_expired_invocation_leaves_nothing_pending(client, transport, monkeypatch):
    """Nothing-leaks invariant (hdp-spec/HDP-0.md §7): after a terminal outcome — here, an
    ack timeout — the invocation_id is absent from the pending table."""
    from hermes_device_plugin import config

    monkeypatch.setattr(config, "ACK_TIMEOUT_S", 0.2)
    ws, device_id = await _connect_and_hello(client)

    async def _never_ack():
        await ws.receive(timeout=5)  # the invoke frame; do nothing with it

    server_task = asyncio.create_task(_never_ack())
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {}},
        deadline_ms=2000,
    )
    result = await transport.invoke(req)
    await server_task
    assert result.error["code"] == "device_offline"
    assert transport._invocations.is_pending(result.invocation_id) is False
    await ws.close()
