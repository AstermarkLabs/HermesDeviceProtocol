"""M1 conformance suite v1 (m1-plan.md §7) — one test per in-scope failure-matrix row, each
driving the real `hdp-node` CLI as a subprocess (except the two rows that need a hand-crafted raw
frame, and the zero-node row that needs no node at all) against a real `EmbeddedTransport` bound
to a real TCP socket.

Explicitly deferred rows — not silently omitted: `bridge_unavailable` (needs the M2 control
socket), `approval_denied` / `approval_timeout` / `policy_denied` / `revoked` (need M3's policy
engine), `ambiguous_device` for the multi-node case (M4 — M1 only covers zero-node and
single-node resolution).
"""

from __future__ import annotations

import asyncio
import json
import logging

import aiohttp
import pytest
from harness import start_node, stop_node, wait_for_device
from hdp_proto.envelope import Envelope
from hdp_proto.errors import ErrorCode
from hermes_device_plugin.transport.base import InvokeRequest

pytestmark = pytest.mark.timeout(20)


def _echo_request(device_id: str, *, deadline_ms: int) -> InvokeRequest:
    return InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {"x": 1}},
        deadline_ms=deadline_ms,
    )


async def test_never_ack_yields_device_offline(bridge, bridge_url):
    proc = await start_node(bridge_url, faults=("never-ack",))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=2000))
        assert result.ok is False
        assert result.error["code"] == ErrorCode.DEVICE_OFFLINE.value
    finally:
        await stop_node(proc)


async def test_slow_result_yields_invocation_timeout(bridge, bridge_url):
    proc = await start_node(bridge_url, faults=("slow-result=4000",))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=500))
        assert result.ok is False
        assert result.error["code"] == ErrorCode.INVOCATION_TIMEOUT.value
    finally:
        await stop_node(proc)


async def test_drop_connection_mid_call_yields_immediate_device_offline(bridge, bridge_url):
    proc = await start_node(bridge_url, faults=("drop-connection-mid-call",))
    try:
        device = await wait_for_device(bridge)
        loop = asyncio.get_running_loop()
        start = loop.time()
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=30_000))
        elapsed = loop.time() - start
        assert result.ok is False
        assert result.error["code"] == ErrorCode.DEVICE_OFFLINE.value
        assert elapsed < 5.0, "must not wait anywhere near the 30s deadline"
    finally:
        await stop_node(proc)


async def test_ignore_cancel_leaves_clean_state_and_logs_the_late_result(
    bridge, bridge_url, caplog
):
    """Covers two matrix rows at once: `ignore-cancel` (the bridge's best-effort cancel is not
    honored; pending state is still clean) and "late result after cancel" (the plugin side is
    silent, the bridge side logs `late_result`) — the second is the direct consequence of the
    first for this fault combination, over the real socket."""
    caplog.set_level(logging.INFO)
    proc = await start_node(bridge_url, faults=("slow-result=4000", "ignore-cancel"))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=500))
        assert result.error["code"] == ErrorCode.INVOCATION_TIMEOUT.value
        # `bridge._invocations` (private) is read here deliberately, not a violation of M1-4's
        # "no test imports `hdp_reference_node` internals" rule — that rule is about the *node*
        # subprocess, driven only via `--fault` flags (see `harness.start_node`). This is the
        # *bridge's* own pending-invocation table, and asserting it's empty post-terminal-state is
        # the actual nothing-leaks invariant m1-plan.md §6/§7 calls for.
        assert bridge._invocations.is_pending(result.invocation_id) is False

        # Let the node's ignored-cancel, still-in-flight result arrive and be dropped.
        await asyncio.sleep(4.0)
        assert "late_result" in caplog.text
        assert bridge._invocations.is_pending(result.invocation_id) is False
    finally:
        await stop_node(proc)


async def test_malformed_result_is_rejected(bridge, bridge_url):
    proc = await start_node(bridge_url, faults=("malformed-result",))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=2000))
        assert result.ok is False
        assert result.error["code"] == ErrorCode.MALFORMED_RESULT.value
    finally:
        await stop_node(proc)


async def test_stale_schema_is_rejected_and_logged(bridge, bridge_url, caplog):
    caplog.set_level(logging.WARNING)
    proc = await start_node(bridge_url, faults=("stale-schema",))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=2000))
        assert result.ok is False
        assert result.error["code"] == ErrorCode.MALFORMED_RESULT.value
        assert "schema_drift" in caplog.text
    finally:
        await stop_node(proc)


async def test_duplicate_result_second_send_has_no_effect(bridge, bridge_url):
    proc = await start_node(bridge_url, faults=("duplicate-result",))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=2000))
        assert result.ok is True
        assert result.data == {"payload": {"x": 1}}
        # The duplicate (identical envelope id) is dropped by the dedupe backstop before it can
        # reach the pending table, which is already empty by the time it arrives regardless.
        await asyncio.sleep(0.2)
    finally:
        await stop_node(proc)


async def test_malformed_envelope_gets_an_error_reply_and_stays_open(bridge_url):
    async with aiohttp.ClientSession() as session, session.ws_connect(bridge_url) as ws:
        await ws.send_str("not json at all")
        msg = await ws.receive(timeout=5)
        envelope = Envelope.from_wire(json.loads(msg.data))
        assert envelope.type == "error"
        assert not ws.closed


async def test_version_mismatch_closes_before_any_reply(bridge_url):
    async with aiohttp.ClientSession() as session, session.ws_connect(bridge_url) as ws:
        await ws.send_str(
            json.dumps(
                {
                    "hdp": "99",
                    "type": "hello",
                    "id": "x",
                    "ts": 0,
                    "corr": None,
                    "payload": {"credential": "must-never-be-read"},
                }
            )
        )
        msg = await ws.receive(timeout=5)
        assert msg.type in (
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.CLOSED,
        )


async def test_no_matching_device_when_zero_nodes_connected():
    """In-scope zero-node case (m1-plan.md §7's deferral note). Exercised through `engine.py`'s
    real device-resolution step — `no_matching_device` is raised there, before any transport is
    touched, so this deliberately does not use the `bridge`/`bridge_url` fixtures."""
    from hermes_device_plugin import engine
    from hermes_device_plugin.runtime import get_runtime

    try:
        raw = await engine.invoke("diagnostics.echo", [1], {"payload": {}}, {})
        result = json.loads(raw)
        assert result["ok"] is False
        assert result["error"]["code"] == ErrorCode.NO_MATCHING_DEVICE.value
    finally:
        get_runtime().close()
        get_runtime.reset()
