"""Direct wire-level tests for `hdp_bridge.server` — a fake "node" is a raw aiohttp WebSocket
test client speaking HDP/0 by hand, not the real reference node (that's `hdp-reference-node`,
exercised end to end by `tests/conformance/`). These tests exist to catch wire-shape bugs close
to the code that produces them.

Uses `aiohttp.test_utils` directly against `server.build_app(...)` — bypassing `HdpServer`'s real
`AppRunner`/`TCPSite` bind entirely, since these tests only need the `Application`'s
routing/dispatch, not a real bound socket. `NodeConnection` is wired directly to a bare
`RegistryMem`/`InvocationsMem`/connections/descriptors state here (the same wiring
`EmbeddedTransport._make_connection` used to do at M1) — the ack-timeout/execution-deadline
`invoke()` orchestration that used to live in `hermes_device_plugin.transport.embedded` is not
part of this module and is ported into `hdp_bridge` by a later M2 task, so those round-trip
invoke tests stay out of this file.
"""

from __future__ import annotations

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer
from hdp_bridge import server as _server
from hdp_bridge.connection import NodeConnection
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import RegistryMem
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Hello

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
    """The same shared-state wiring `EmbeddedTransport` used to own at M1: one `RegistryMem`,
    one `InvocationsMem`, and the `connections`/`descriptors` dicts every `NodeConnection` on this
    app shares."""

    def __init__(self) -> None:
        self.registry = RegistryMem()
        self.invocations = InvocationsMem()
        self.connections: dict[str, NodeConnection] = {}
        self.descriptors: dict = {}

    def make_connection(self, ws: object) -> NodeConnection:
        return NodeConnection(
            ws,  # type: ignore[arg-type]
            registry=self.registry,
            invocations=self.invocations,
            connections=self.connections,
            descriptors=self.descriptors,
        )


@pytest.fixture
def harness():
    return _Harness()


@pytest.fixture
async def client(harness):
    app = _server.build_app(harness.make_connection)
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


async def test_hello_welcome_handshake_registers_the_device(client, harness):
    ws, device_id = await _connect_and_hello(client)
    devices = harness.registry.list_devices()
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
