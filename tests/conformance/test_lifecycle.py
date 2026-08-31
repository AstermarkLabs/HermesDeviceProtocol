"""M4 live lifecycle and version-resolution behavior over the public protocol."""

from __future__ import annotations

import asyncio
import base64
import json

import aiohttp
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from harness import prepare_usb_enrollment, start_node, stop_node
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope
from hdp_proto.messages import CapabilitiesMsg, Challenge, Hello, Proof, ResultMsg, Welcome
from hermes_device_plugin import engine, runtime, tools
from hermes_device_plugin.transport.base import BridgeStatus, InvokeRequest

pytestmark = pytest.mark.timeout(30)

_ECHO_V1 = CapabilityDescriptor(
    name="diagnostics.echo",
    version=1,
    input_schema={"type": "object"},
    output_schema={
        "type": "object",
        "properties": {"payload": {"type": "object"}},
        "required": ["payload"],
    },
)
_NOTIFY_V1 = CapabilityDescriptor(
    name="notifications.send",
    version=1,
    input_schema={"type": "object"},
    output_schema={"type": "object"},
)

_PAIR_CONTEXT = b"HDP/0 pair-challenge\x00"
_AUTH_CONTEXT = b"HDP/0 auth-challenge\x00"


def _new_device_key() -> tuple[ec.EllipticCurvePrivateKey, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode("ascii")
    return private_key, public_key


def _sign(private_key: ec.EllipticCurvePrivateKey, context: bytes, nonce: str) -> str:
    signature = private_key.sign(context + base64.b64decode(nonce), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("ascii")


async def _receive_envelope(ws: aiohttp.ClientWebSocketResponse) -> Envelope:
    return Envelope.from_wire(json.loads((await ws.receive(timeout=5)).data))


async def _enroll_raw_node(
    ws: aiohttp.ClientWebSocketResponse,
    *,
    name: str,
    capabilities: tuple[CapabilityDescriptor, ...],
) -> tuple[Welcome, ec.EllipticCurvePrivateKey]:
    private_key, public_key = _new_device_key()
    hello = Hello(
        hdp_versions=(0,),
        device_name=name,
        capabilities=capabilities,
        device_pubkey=public_key,
        enrollment_id=prepare_usb_enrollment(public_key),
    )
    await ws.send_str(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    challenge = Challenge.from_wire((await _receive_envelope(ws)).payload)
    await ws.send_str(
        json.dumps(
            Envelope.new(
                "proof", Proof(_sign(private_key, _PAIR_CONTEXT, challenge.nonce)).to_wire()
            ).to_wire()
        )
    )
    return Welcome.from_wire((await _receive_envelope(ws)).payload), private_key


async def _authenticate_raw_node(
    ws: aiohttp.ClientWebSocketResponse,
    *,
    name: str,
    capabilities: tuple[CapabilityDescriptor, ...],
    credential: str,
    private_key: ec.EllipticCurvePrivateKey,
) -> Welcome:
    hello = Hello(
        hdp_versions=(0,), device_name=name, capabilities=capabilities, credential=credential
    )
    await ws.send_str(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    challenge = Challenge.from_wire((await _receive_envelope(ws)).payload)
    await ws.send_str(
        json.dumps(
            Envelope.new(
                "proof", Proof(_sign(private_key, _AUTH_CONTEXT, challenge.nonce)).to_wire()
            ).to_wire()
        )
    )
    return Welcome.from_wire((await _receive_envelope(ws)).payload)


def _echo_request(
    *,
    acceptable_versions: tuple[int, ...] = (1,),
    requested_device_id: str | None = None,
    deadline_ms: int = 2_000,
) -> InvokeRequest:
    return InvokeRequest(
        capability="diagnostics.echo",
        acceptable_versions=acceptable_versions,
        requested_device_id=requested_device_id,
        args={"payload": {"marker": "m4"}},
        deadline_ms=deadline_ms,
    )


async def _wait_for_online_devices(bridge, count: int, *, timeout_s: float = 10.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        online = [device for device in await bridge.list_devices() if device.online]
        if len(online) == count:
            return sorted(online, key=lambda device: device.device_id)
        await asyncio.sleep(0.05)
    raise TimeoutError(f"expected {count} online device(s)")


async def test_appear_then_disappear_changes_the_very_next_implicit_resolution(bridge, bridge_url):
    absent = await bridge.invoke(_echo_request())
    assert absent.error["code"] == "no_matching_device"

    proc = await start_node(bridge_url, name="appearing-node")
    try:
        await _wait_for_online_devices(bridge, 1)
        present = await bridge.invoke(_echo_request())
        assert present.ok is True
    finally:
        await stop_node(proc)

    await _wait_for_online_devices(bridge, 0)
    gone = await bridge.invoke(_echo_request())
    assert gone.error["code"] == "no_matching_device"


async def test_multiple_candidates_are_structured_then_one_policy_default_selects(
    bridge, bridge_url, _hermes_home
):
    proc_a = await start_node(bridge_url, name="Alpha")
    proc_b = await start_node(bridge_url, name="Beta")
    try:
        async with aiohttp.ClientSession() as session, session.ws_connect(bridge_url) as ws:
            welcome, _ = await _enroll_raw_node(
                ws, name="Notifications only", capabilities=(_NOTIFY_V1,)
            )
            noncandidate_id = welcome.device_id
            all_devices = await _wait_for_online_devices(bridge, 3)
            devices = [
                device
                for device in all_devices
                if any(cap.name == "diagnostics.echo" for cap in device.capabilities)
            ]

            explicit = await bridge.invoke(_echo_request(requested_device_id=devices[0].device_id))
            assert explicit.ok is True

            ambiguous = await bridge.invoke(_echo_request())
            assert ambiguous.error["code"] == "ambiguous_device"
            assert ambiguous.error["candidates"] == [
                {"device_id": device.device_id, "friendly_name": device.friendly_name}
                for device in devices
            ]

            policy_path = _hermes_home / "hdp" / "policy.yaml"
            policy_path.write_text(
                "version: 1\n"
                "defaults:\n  diagnostics.echo: always\n"
                "devices: {}\n"
                f"default_device:\n  diagnostics.echo: {noncandidate_id}\n"
            )
            assert (await bridge.ctl_policy_reload())["ok"] is True
            still_ambiguous = await bridge.invoke(_echo_request())
            assert still_ambiguous.error["code"] == "ambiguous_device"

            selected = devices[1]
            policy_path.write_text(
                "version: 1\n"
                "defaults:\n  diagnostics.echo: always\n"
                "devices: {}\n"
                f"default_device:\n  diagnostics.echo: {selected.device_id}\n"
            )
            reload_result = await bridge.ctl_policy_reload()
            assert reload_result["ok"] is True

            resolved = await bridge.invoke(_echo_request())
            assert resolved.ok is True
    finally:
        await stop_node(proc_a)
        await stop_node(proc_b)


async def test_highest_mutual_version_is_dispatched_and_no_overlap_carries_both_lists(
    bridge, bridge_url
):
    echo_v2 = CapabilityDescriptor(
        name=_ECHO_V1.name,
        version=2,
        input_schema=_ECHO_V1.input_schema,
        output_schema=_ECHO_V1.output_schema,
    )
    async with aiohttp.ClientSession() as session, session.ws_connect(bridge_url) as ws:
        welcome, _ = await _enroll_raw_node(
            ws, name="version-node", capabilities=(_ECHO_V1, echo_v2)
        )
        device_id = welcome.device_id
        invoke_task = asyncio.create_task(
            bridge.invoke(_echo_request(acceptable_versions=(1, 2), requested_device_id=device_id))
        )
        invoke = Envelope.from_wire(json.loads((await ws.receive(timeout=5)).data))
        assert invoke.payload["version"] == 2
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=invoke.corr).to_wire()))
        result = ResultMsg(ok=True, data={"payload": {}}, error=None)
        await ws.send_str(
            json.dumps(Envelope.new("result", result.to_wire(), corr=invoke.corr).to_wire())
        )
        negotiated = await invoke_task
        assert negotiated.ok is True

        stepped_down_task = asyncio.create_task(
            bridge.invoke(_echo_request(acceptable_versions=(1,), requested_device_id=device_id))
        )
        stepped_down_invoke = Envelope.from_wire(json.loads((await ws.receive(timeout=5)).data))
        assert stepped_down_invoke.payload["version"] == 1
        await ws.send_str(
            json.dumps(Envelope.new("ack", {}, corr=stepped_down_invoke.corr).to_wire())
        )
        await ws.send_str(
            json.dumps(
                Envelope.new("result", result.to_wire(), corr=stepped_down_invoke.corr).to_wire()
            )
        )
        assert (await stepped_down_task).ok is True

        echo_v3 = CapabilityDescriptor(
            name=_ECHO_V1.name,
            version=3,
            input_schema=_ECHO_V1.input_schema,
            output_schema=_ECHO_V1.output_schema,
        )
        replacement = CapabilitiesMsg(capabilities=(_ECHO_V1, echo_v3))
        await ws.send_str(json.dumps(Envelope.new("capabilities", replacement.to_wire()).to_wire()))
        for _ in range(100):
            versions = [
                cap.version
                for cap in (await bridge.list_devices())[0].capabilities
                if cap.name == "diagnostics.echo"
            ]
            if versions == [1, 3]:
                break
            await asyncio.sleep(0.01)
        assert versions == [1, 3]

        noncontiguous_task = asyncio.create_task(
            bridge.invoke(_echo_request(acceptable_versions=(2, 3), requested_device_id=device_id))
        )
        noncontiguous = Envelope.from_wire(json.loads((await ws.receive(timeout=5)).data))
        assert noncontiguous.payload["version"] == 3
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=noncontiguous.corr).to_wire()))
        await ws.send_str(
            json.dumps(Envelope.new("result", result.to_wire(), corr=noncontiguous.corr).to_wire())
        )
        assert (await noncontiguous_task).ok is True

    await _wait_for_online_devices(bridge, 0)
    incompatible_proc = await start_node(bridge_url, capability_versions=("diagnostics.echo@99",))
    try:
        device = (await _wait_for_online_devices(bridge, 1))[0]
        incompatible = await bridge.invoke(
            _echo_request(acceptable_versions=(1, 2), requested_device_id=device.device_id)
        )
        assert incompatible.error["code"] == "version_incompatible"
        assert incompatible.error["node_supports"] == [99]
        assert incompatible.error["plugin_supports"] == [1, 2]
    finally:
        await stop_node(incompatible_proc)


async def test_readvertisement_is_full_set_and_inflight_validation_uses_dispatch_schema(
    bridge, bridge_url
):
    async with aiohttp.ClientSession() as session, session.ws_connect(bridge_url) as ws:
        welcome, _ = await _enroll_raw_node(ws, name="raw-lifecycle-node", capabilities=(_ECHO_V1,))
        device_id = welcome.device_id
        await _wait_for_online_devices(bridge, 1)

        invoke_task = asyncio.create_task(
            bridge.invoke(_echo_request(requested_device_id=device_id, deadline_ms=5_000))
        )
        invoke = Envelope.from_wire(json.loads((await ws.receive(timeout=5)).data))
        assert invoke.type == "invoke"
        assert invoke.payload["version"] == 1
        await ws.send_str(json.dumps(Envelope.new("ack", {}, corr=invoke.corr).to_wire()))

        replacement = CapabilitiesMsg(capabilities=(_NOTIFY_V1,))
        await ws.send_str(json.dumps(Envelope.new("capabilities", replacement.to_wire()).to_wire()))
        for _ in range(100):
            devices = await bridge.list_devices()
            names = [capability.name for capability in devices[0].capabilities]
            if names == ["notifications.send"]:
                break
            await asyncio.sleep(0.01)
        assert names == ["notifications.send"]

        result = ResultMsg(ok=True, data={"payload": {}}, error=None)
        await ws.send_str(
            json.dumps(Envelope.new("result", result.to_wire(), corr=invoke.corr).to_wire())
        )
        resolved = await invoke_task
        assert resolved.ok is True

        next_invoke = await bridge.invoke(_echo_request())
        assert next_invoke.error["code"] == "no_matching_device"


async def test_disconnect_midflight_fails_immediately(bridge, bridge_url):
    async with aiohttp.ClientSession() as session, session.ws_connect(bridge_url) as ws:
        welcome, _ = await _enroll_raw_node(ws, name="disconnecting-node", capabilities=(_ECHO_V1,))
        device_id = welcome.device_id

        loop = asyncio.get_running_loop()
        started = loop.time()
        invoke_task = asyncio.create_task(
            bridge.invoke(_echo_request(requested_device_id=device_id, deadline_ms=30_000))
        )
        invoke = Envelope.from_wire(json.loads((await ws.receive(timeout=5)).data))
        assert invoke.type == "invoke"
        await ws.close()
        result = await invoke_task

        assert result.error["code"] == "device_offline"
        assert loop.time() - started < 5.0


async def test_same_device_reconnect_replaces_connection_without_cross_failing_calls(
    bridge, bridge_url
):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(bridge_url) as old_ws:
            old_welcome, private_key = await _enroll_raw_node(
                old_ws, name="reconnecting-node", capabilities=(_ECHO_V1,)
            )
            device_id = old_welcome.device_id
            credential = old_welcome.credential
            assert credential is not None

            old_task = asyncio.create_task(
                bridge.invoke(_echo_request(requested_device_id=device_id, deadline_ms=30_000))
            )
            old_invoke = Envelope.from_wire(json.loads((await old_ws.receive(timeout=5)).data))
            await old_ws.send_str(
                json.dumps(Envelope.new("ack", {}, corr=old_invoke.corr).to_wire())
            )

            async with session.ws_connect(bridge_url) as replacement_ws:
                replacement_welcome = await _authenticate_raw_node(
                    replacement_ws,
                    name="reconnecting-node",
                    capabilities=(_ECHO_V1,),
                    credential=credential,
                    private_key=private_key,
                )
                assert replacement_welcome.device_id == device_id

                new_task = asyncio.create_task(
                    bridge.invoke(_echo_request(requested_device_id=device_id))
                )
                new_invoke = Envelope.from_wire(
                    json.loads((await replacement_ws.receive(timeout=5)).data)
                )
                result = ResultMsg(ok=True, data={"payload": {}}, error=None)
                await replacement_ws.send_str(
                    json.dumps(Envelope.new("ack", {}, corr=new_invoke.corr).to_wire())
                )
                await replacement_ws.send_str(
                    json.dumps(
                        Envelope.new("result", result.to_wire(), corr=new_invoke.corr).to_wire()
                    )
                )
                assert (await new_task).ok is True

                await old_ws.close()
                old_result = await old_task
                assert old_result.error["code"] == "device_offline"

                after_old_disconnect = asyncio.create_task(
                    bridge.invoke(_echo_request(requested_device_id=device_id))
                )
                next_invoke = Envelope.from_wire(
                    json.loads((await replacement_ws.receive(timeout=5)).data)
                )
                await replacement_ws.send_str(
                    json.dumps(Envelope.new("ack", {}, corr=next_invoke.corr).to_wire())
                )
                await replacement_ws.send_str(
                    json.dumps(
                        Envelope.new("result", result.to_wire(), corr=next_invoke.corr).to_wire()
                    )
                )
                assert (await after_old_disconnect).ok is True


async def test_check_fn_is_not_an_invocation_gate(bridge, bridge_url, monkeypatch):
    proc = await start_node(bridge_url, name="visible-or-not")
    try:
        await _wait_for_online_devices(bridge, 1)
        runtime._update_availability(status=BridgeStatus(healthy=False), devices=[])
        assert tools.echo_available() is False

        class _Runtime:
            transport = bridge

        monkeypatch.setattr(engine, "get_runtime", lambda: _Runtime())
        raw = await engine.invoke("diagnostics.echo", [1], {"payload": {}}, {})
        assert json.loads(raw)["ok"] is True
    finally:
        runtime._reset_availability_for_tests()
        await stop_node(proc)
