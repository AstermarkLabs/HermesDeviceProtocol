"""`engine.invoke()`'s resolution tree against a fake `BridgeTransport` — no sockets, no real
`HDPRuntime` thread, so the whole target-selection decision tree is fast and exhaustive
(design §7). Exercises the one M0-reachable failure path (`no_matching_device`, D3) plus the
happy path and transport-error passthrough.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from hermes_device_plugin import engine
from hermes_device_plugin.transport.base import DeviceInfo, InvokeResult


class _FakeRuntime:
    def __init__(self, transport):
        self.transport = transport


class _FakeTransport:
    def __init__(self, devices, invoke_result=None):
        self._devices = devices
        self._invoke_result = invoke_result

    async def list_devices(self):
        return self._devices

    async def invoke(self, req):
        if self._invoke_result is not None:
            return self._invoke_result
        return InvokeResult(
            invocation_id="01FAKE0000000000000000000", ok=True, data={"echo": req.args}
        )


def _device(device_id="dev1"):
    return DeviceInfo(device_id=device_id, friendly_name="d", platform="linux", online=True)


def _patched(transport):
    return patch.object(engine, "get_runtime", return_value=_FakeRuntime(transport))


async def test_invoke_with_zero_devices_returns_no_matching_device():
    with _patched(_FakeTransport([])):
        result = json.loads(await engine.invoke("notifications.send", [1], {}, {}))
    assert result["ok"] is False
    assert result["error"]["code"] == "no_matching_device"
    assert "device_status_get" in result["error"]["hint"]


async def test_invoke_resolves_sole_candidate_and_succeeds():
    with _patched(_FakeTransport([_device()])):
        result = json.loads(await engine.invoke("notifications.send", [1], {"title": "x"}, {}))
    assert result == {"ok": True, "data": {"echo": {"title": "x"}}}


async def test_invoke_with_explicit_device_id_no_match_returns_no_matching_device():
    with _patched(_FakeTransport([_device("dev1")])):
        result = json.loads(
            await engine.invoke("notifications.send", [1], {}, {}, device_id="dev2")
        )
    assert result["ok"] is False
    assert result["error"]["code"] == "no_matching_device"


async def test_invoke_with_explicit_device_id_match_succeeds():
    with _patched(_FakeTransport([_device("dev1"), _device("dev2")])):
        result = json.loads(
            await engine.invoke("notifications.send", [1], {}, {}, device_id="dev2")
        )
    assert result["ok"] is True


async def test_invoke_propagates_transport_error():
    error = {"code": "not_implemented", "message": "x", "hint": "y"}
    transport = _FakeTransport(
        [_device()], invoke_result=InvokeResult(invocation_id="x", ok=False, error=error)
    )
    with _patched(transport):
        result = json.loads(await engine.invoke("notifications.send", [1], {}, {}))
    assert result == {"ok": False, "error": error}
