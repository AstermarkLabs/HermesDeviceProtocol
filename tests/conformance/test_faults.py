"""M1 conformance suite v1 (m1-plan.md §7) — one test per in-scope failure-matrix row, each
driving the real `hdp-node` CLI as a subprocess (except the two rows that need a hand-crafted raw
frame, and the zero-node row that needs no node at all) against a real `SocketTransport` (M2)
talking over a Unix control socket to a real `hdp serve` subprocess, which in turn binds a
real TCP socket for nodes.

Explicitly deferred rows — not silently omitted: `bridge_unavailable` (needs the M2 control
socket), `approval_denied` / `approval_timeout` / `policy_denied` / `revoked` (need M3's policy
engine), `ambiguous_device` for the multi-node case (M4 — M1 only covers zero-node and
single-node resolution).
"""

from __future__ import annotations

import asyncio
import json

import aiohttp
import pytest
from harness import start_node, stop_node, wait_for_device, wait_for_log
from hdp_proto.envelope import Envelope
from hdp_proto.errors import ErrorCode
from hermes_device_plugin.transport.base import InvokeRequest

pytestmark = pytest.mark.timeout(30)


def _echo_request(device_id: str, *, deadline_ms: int) -> InvokeRequest:
    return InvokeRequest(
        capability="diagnostics.echo",
        acceptable_versions=(1,),
        requested_device_id=device_id,
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
    bridge, bridge_url, bridge_log
):
    """Covers two matrix rows at once: `ignore-cancel` (the bridge's best-effort cancel is not
    honored; pending state is still clean) and "late result after cancel" (the plugin side is
    silent, the bridge side logs `late_result`) — the second is the direct consequence of the
    first for this fault combination, over the real socket.

    `bridge_log` reads the real `hdp serve` subprocess's own stdout/stderr — `caplog` only
    captures logging within the test process, and as of M2 the bridge is a separate OS process,
    so the `late_result` log record it emits (`hdp_bridge/connection.py`) is invisible to
    `caplog` entirely."""
    proc = await start_node(bridge_url, faults=("slow-result=4000", "ignore-cancel"))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=500))
        assert result.error["code"] == ErrorCode.INVOCATION_TIMEOUT.value

        # Let the node's ignored-cancel, still-in-flight result arrive and be dropped. The node
        # dispatches frames on this connection sequentially (`hdp_reference_node`'s
        # `async for msg in ws` loop awaits each `_handle_invoke` to completion before reading the
        # next frame), so it is still asleep inside the first invocation's `slow-result=4000` and
        # will not even see a second `invoke` frame until that sleep — and the late result it
        # triggers — has passed.
        #
        # Waiting on the log line itself, rather than sleeping a fixed 4s and then asserting,
        # does both jobs at once and races neither: `late_result` appearing in `bridge_log` *is*
        # the proof the node's late result has arrived and been dropped, which is also exactly
        # the moment the node is free to dispatch the second invoke below. The timeout must
        # comfortably clear the node's own 4s `slow-result` delay.
        await wait_for_log(bridge_log, "late_result", timeout=8.0)

        # `bridge._invocations` was `EmbeddedTransport`'s private pending-invocation table,
        # readable in-process. As of M2 the bridge is a separate `hdp serve` subprocess —
        # that table now lives inside the daemon, unreachable from the test process. The
        # nothing-leaks invariant (m1-plan.md §6/§7) is instead asserted the only way it can be
        # from outside: a second `invoke()` against the same device, now that the node is free to
        # dispatch again, must still succeed cleanly. If the first invocation's entry — or the late
        # result that just arrived for it — had been left dangling in the daemon's pending table
        # (e.g. blocking new invocations for the device, or corrupting the wrong entry), this call
        # would hang, error, or return the wrong data instead of a fresh, correct echo.
        #
        # `--fault` flags are process-wide on the reference node (parsed once at startup,
        # `faults.py`'s `FaultConfig`), not per-invocation — this node was started with
        # `slow-result=4000`, so *every* invocation it handles, including this second one, still
        # waits ~4s before replying. `deadline_ms` here must comfortably clear that same 4s, or
        # this call would spuriously time out for a reason that has nothing to do with the
        # nothing-leaks invariant actually under test.
        second = await bridge.invoke(_echo_request(device.device_id, deadline_ms=6000))
        assert second.ok is True
        assert second.data == {"payload": {"x": 1}}
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


async def test_stale_schema_is_rejected_and_logged(bridge, bridge_url, bridge_log):
    """See `test_ignore_cancel_leaves_clean_state_and_logs_the_late_result`'s docstring for why
    this reads `bridge_log` (the bridge subprocess's own stdout) rather than `caplog`:
    `schema_drift` is logged inside `hdp_bridge/control.py`, in the daemon subprocess."""
    proc = await start_node(bridge_url, faults=("stale-schema",))
    try:
        device = await wait_for_device(bridge)
        result = await bridge.invoke(_echo_request(device.device_id, deadline_ms=2000))
        assert result.ok is False
        assert result.error["code"] == ErrorCode.MALFORMED_RESULT.value
        # Poll rather than assert immediately: `invoke()`'s reply and the daemon's `schema_drift`
        # log line reach this process by two independent paths (control socket vs. daemon stdout
        # -> pipe -> conftest's `_drain()` task), with nothing synchronizing them.
        await wait_for_log(bridge_log, "schema_drift", timeout=2.0)
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


async def test_no_matching_device_when_zero_nodes_connected(bridge):
    """In-scope zero-node case (m1-plan.md §7's deferral note): with the bridge up but no node
    connected, an invocation must fail with `no_matching_device`.

    Historically this exercised `engine.py`'s plugin-side device-resolution step and deliberately
    did *not* start a bridge. As of M4 (`engine.invoke` now forwards the unresolved request to
    the daemon, which owns resolution), the plugin can no longer reach `no_matching_device`
    without a bridge — there is no plugin-side resolution step left. The honest equivalent is to
    drive the daemon's own resolution path: start the bridge, connect zero nodes, invoke, and
    assert the daemon returns `no_matching_device` from its empty registry.
    """
    result = await bridge.invoke(
        InvokeRequest(
            capability="diagnostics.echo",
            acceptable_versions=(1,),
            requested_device_id=None,
            args={"payload": {}},
            deadline_ms=2000,
        )
    )
    assert result.ok is False
    assert result.error["code"] == ErrorCode.NO_MATCHING_DEVICE.value
