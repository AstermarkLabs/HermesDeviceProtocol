"""M5 Android-shaped protocol conformance.

The fixture is intentionally driven through HDP frames and the public bridge transport.  No
reference-node module, handler, or Android implementation detail is imported here.
"""

from __future__ import annotations

import asyncio

import pytest
from android_node_fixture import _ECHO_DESCRIPTOR, ANDROID_CAPABILITIES, AndroidNodeFixture
from harness import mint_pairing_code, wait_for_device
from hermes_device_plugin.transport.base import InvokeRequest

pytestmark = pytest.mark.timeout(30)


async def _wait_for_capabilities(bridge, expected: set[str]) -> None:
    deadline = asyncio.get_running_loop().time() + 5
    while asyncio.get_running_loop().time() < deadline:
        devices = await bridge.list_devices()
        online = [device for device in devices if device.online]
        if online and {capability.name for capability in online[0].capabilities} == expected:
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"capability set did not become {expected!r}")


async def test_android_profile_pair_invoke_reconnect_and_local_policy(
    bridge, bridge_url, _hermes_home
):
    node = AndroidNodeFixture()
    pair_code = await mint_pairing_code()
    try:
        welcome = await node.connect(bridge_url, pair_code=pair_code)
        device = await wait_for_device(bridge)
        assert welcome.device_id == device.device_id
        assert {capability.name for capability in device.capabilities} == {
            capability.name for capability in ANDROID_CAPABILITIES
        }

        policy_path = _hermes_home / "hdp" / "policy.yaml"
        policy_path.write_text(
            "version: 1\n"
            "defaults:\n"
            "  notifications.send: always\n"
            "  device.status: always\n"
            "  diagnostics.echo: always\n"
            "devices: {}\n"
            "default_device: {}\n",
            encoding="utf-8",
        )
        assert (await bridge.ctl_policy_reload())["ok"] is True

        status = await bridge.invoke(
            InvokeRequest("device.status", (1,), device.device_id, {}, 2_000)
        )
        assert status.ok is True
        assert status.data == {"platform": "android", "uptime_s": 0}

        notification = await bridge.invoke(
            InvokeRequest(
                "notifications.send",
                (1,),
                device.device_id,
                {"title": "M5", "body": "protocol"},
                2_000,
            )
        )
        assert notification.ok is True
        assert node.executed_notifications == [{"title": "M5", "body": "protocol"}]

        await node.replace_capabilities((_ECHO_DESCRIPTOR,))
        await _wait_for_capabilities(bridge, {"diagnostics.echo"})
        denied = await bridge.invoke(
            InvokeRequest("diagnostics.echo", (1,), device.device_id, {"payload": {}}, 2_000)
        )
        assert denied.ok is False
        assert denied.error["code"] == "policy_denied"

        reconnected = await node.reconnect(bridge_url)
        assert reconnected.device_id == device.device_id
        await _wait_for_capabilities(bridge, {"diagnostics.echo"})
    finally:
        await node.close()
