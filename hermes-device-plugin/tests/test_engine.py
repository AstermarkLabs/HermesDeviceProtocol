"""The plugin forwards unresolved invocations to the daemon-owned live resolver."""

from __future__ import annotations

import json
from unittest.mock import patch

from hermes_device_plugin import engine
from hermes_device_plugin.transport.base import InvokeResult


class _FakeRuntime:
    def __init__(self, transport):
        self.transport = transport


class _FakeTransport:
    def __init__(self, invoke_result=None):
        self._invoke_result = invoke_result
        self.requests = []

    async def invoke(self, req):
        self.requests.append(req)
        if self._invoke_result is not None:
            return self._invoke_result
        return InvokeResult(
            invocation_id="01FAKE0000000000000000000", ok=True, data={"echo": req.args}
        )


def _patched(transport):
    return patch.object(engine, "get_runtime", return_value=_FakeRuntime(transport))


async def test_invoke_forwards_unresolved_request_and_strips_routing_device():
    """Reintroducing plugin-side list/select logic or leaking `device` to the node fails here."""
    transport = _FakeTransport()
    with _patched(transport):
        result = json.loads(
            await engine.invoke(
                "notifications.send",
                [1, 2],
                {"device": "dev_target", "title": "x"},
                {"session_id": "session_1"},
                device_id="dev_target",
            )
        )

    assert result == {"ok": True, "data": {"echo": {"title": "x"}}}
    request = transport.requests[0]
    assert request.capability == "notifications.send"
    assert request.acceptable_versions == (1, 2)
    assert request.requested_device_id == "dev_target"
    assert request.args == {"title": "x"}
    assert request.meta == {"session_id": "session_1"}


async def test_invoke_propagates_transport_error():
    error = {"code": "not_implemented", "message": "x", "hint": "y"}
    transport = _FakeTransport(invoke_result=InvokeResult(invocation_id="x", ok=False, error=error))
    with _patched(transport):
        result = json.loads(await engine.invoke("notifications.send", [1], {}, {}))
    assert result == {"ok": False, "error": error}
