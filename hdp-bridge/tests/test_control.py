from __future__ import annotations

import asyncio

import pytest
from hdp_bridge.control import ControlServer, read_frame, write_frame
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import RegistryMem
from hdp_bridge.types import DeviceRecord
from hdp_proto.envelope import Envelope


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
