"""M6: the conformance rows run against a real, externally-connected node.

Opt-in and skipped by default, so `make test` is untouched. The assertions here are deliberately
the same ones `test_android_node.py` makes against the in-process fixture — M5's gate is that the
suite can be pointed at an Android endpoint *without changing its assertions*, so anything that
had to be weakened to accommodate a real device would defeat the purpose.

Run it against a live emulator or device after USB bootstrap has completed:

    # Terminal 1 — the operator's own bridge, already serving
    HERMES_HOME=$HOME/.hermes uv run hdp serve

    # Terminal 2
    HDP_EXTERNAL_NODE=1 HERMES_HOME=$HOME/.hermes uv run pytest \\
        tests/conformance/test_external_node.py -s

The `-s` matters: the test prints the USB-bootstrap wait state for the operator.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from conftest import external_node_mode
from harness import wait_for_device
from hermes_device_plugin.transport.base import InvokeRequest

pytestmark = [
    pytest.mark.skipif(
        not external_node_mode(),
        reason="set HDP_EXTERNAL_NODE=1 and connect a real node to run these",
    ),
    # Generous: the operator may need time to complete the physical USB bootstrap.
    pytest.mark.timeout(int(os.environ.get("HDP_EXTERNAL_TIMEOUT_S", "300"))),
]

_PAIRING_WINDOW_S = float(os.environ.get("HDP_EXTERNAL_PAIRING_WINDOW_S", "180"))


async def _await_paired_node(bridge):
    """Return the connected node, pairing one first if none is present.

    Checks before waiting so that a run against an already-paired device is silent and instant.
    A fresh node must be enrolled through the real USB bootstrap; this test never creates a
    remote pairing secret as a side channel.
    """
    for device in await bridge.list_devices():
        if device.online:
            return device

    print("\n\n    Connect the device by USB and complete bootstrap now.\n", flush=True)
    device = await wait_for_device(bridge, timeout_s=_PAIRING_WINDOW_S)
    print(f"    Paired: device_id={device.device_id} platform={device.platform}\n", flush=True)
    return device


async def _wait_for_capabilities(bridge, device_id: str, expected: set[str], *, timeout_s=30.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        for device in await bridge.list_devices():
            if device.device_id == device_id and device.online:
                if {c.name for c in device.capabilities} == expected:
                    return
        await asyncio.sleep(0.2)
    raise TimeoutError(f"capability set did not become {expected!r}")


async def _wait_for_online(bridge, device_id: str, *, online: bool, timeout_s=120.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        for device in await bridge.list_devices():
            if device.device_id == device_id and device.online is online:
                return device
        await asyncio.sleep(0.2)
    raise TimeoutError(f"device {device_id} did not become online={online}")


async def test_external_node_pairs_with_a_stable_android_identity(bridge):
    """M6 exit gate 1 and 2."""
    device = await _await_paired_node(bridge)

    assert device.device_id
    assert device.online is True
    assert device.platform == "android"
    assert {c.name for c in device.capabilities} == {"notifications.send", "device.status"}


async def test_external_node_executes_the_minimal_capability_profile(bridge):
    """M6 exit gate 4's success path, plus the schema conformance FR-6 asks for: the node's
    results are validated against the schemas it advertised before the bridge trusts them."""
    device = await _await_paired_node(bridge)

    status = await bridge.invoke(InvokeRequest("device.status", (1,), device.device_id, {}, 10_000))
    assert status.ok is True, status.error
    assert status.data["platform"] == "android"
    assert isinstance(status.data["uptime_s"], (int, float))

    notification = await bridge.invoke(
        InvokeRequest(
            "notifications.send",
            (1,),
            device.device_id,
            {"title": "M6", "body": "external node"},
            10_000,
        )
    )
    assert notification.ok is True, notification.error
    assert notification.data == {"delivered": True}


async def test_external_node_denies_a_capability_it_does_not_advertise(bridge):
    """M6 exit gate 4's node-local layer. `diagnostics.echo@1` is deliberately outside the
    Android profile, so this must fail without any side effect on the device."""
    device = await _await_paired_node(bridge)

    denied = await bridge.invoke(
        InvokeRequest("diagnostics.echo", (1,), device.device_id, {"payload": {}}, 10_000)
    )
    assert denied.ok is False
    assert denied.error["code"] in {"capability_unsupported", "policy_denied"}


async def test_external_node_keeps_its_identity_across_an_interruption(bridge):
    """M6 exit gate 3. Driven by the operator: background/kill the app, then bring it back."""
    device = await _await_paired_node(bridge)
    device_id = device.device_id

    print("\n    Now background or force-stop the app, then reopen it.\n", flush=True)
    await _wait_for_online(bridge, device_id, online=False)
    print("    Node went offline. Waiting for it to come back...\n", flush=True)
    recovered = await _wait_for_online(bridge, device_id, online=True)

    # Same bridge-issued identity, and the full capability set re-advertised — not a delta, and
    # not a new device_id minted on the node's side.
    assert recovered.device_id == device_id
    await _wait_for_capabilities(bridge, device_id, {"notifications.send", "device.status"})
