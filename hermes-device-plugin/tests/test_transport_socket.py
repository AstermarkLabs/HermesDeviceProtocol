"""`SocketTransport` — the plugin-side client of `hdp_bridge/control.py`'s Unix-socket framing.

Stands up a real `hdp_bridge.daemon.serve()` task of its own (not `HDPRuntime`) — this is the
plugin-side half of Task 6's TDD cycle; the server-side handlers (`ctl_invoke`, `ctl_cancel`,
`ctl_status`) are covered from the daemon side in `hdp-bridge/tests/test_control.py`, using a real
node connection to exercise the ack/deadline race itself. These tests only need zero connected
devices to exercise `SocketTransport`'s own framing, error mapping, and reconnect behavior.

(Was collection-blocked pre-Task-7: importing `hermes_device_plugin` pulled in
`hermes_device_plugin/runtime.py` -> `transport/embedded.py`, which imported the now-relocated
`transport/_connection.py` et al. Task 7 flipped `runtime.py`'s default transport to
`SocketTransport` and deleted `embedded.py`, which fixed that chain — this file collects and
passes normally now. See
`.superpowers/sdd/2026-08-15-m2-registry-pairing-extraction/task-6-report.md` for the manual
smoke-test evidence gathered before Task 7 landed.)
"""

from __future__ import annotations

import asyncio

import pytest
from hermes_device_plugin.transport.base import InvokeRequest
from hermes_device_plugin.transport.socket import SocketTransport


@pytest.fixture
async def bridge_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    from hdp_bridge import daemon

    stop_event = asyncio.Event()
    task = asyncio.create_task(daemon.serve(stop_event=stop_event))
    await asyncio.sleep(0.2)
    yield tmp_path, stop_event, task
    if not stop_event.is_set():
        stop_event.set()
        await asyncio.wait_for(task, timeout=5)


async def test_invoke_against_zero_connected_devices_is_device_offline(bridge_daemon):
    _tmp_path, _stop_event, _task = bridge_daemon
    transport = SocketTransport()
    await transport.start()
    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id="dev_nonexistent",
        args={"payload": {}},
        deadline_ms=1000,
    )
    result = await transport.invoke(req)
    await transport.close()
    assert result.ok is False
    assert result.error["code"] == "device_offline"


async def test_list_devices_is_empty_with_nothing_connected(bridge_daemon):
    transport = SocketTransport()
    await transport.start()
    devices = await transport.list_devices()
    await transport.close()
    assert devices == []


async def test_status_reports_healthy_with_zero_devices(bridge_daemon):
    transport = SocketTransport()
    await transport.start()
    status = await transport.status()
    await transport.close()
    assert status.healthy is True
    assert status.detail == "0 device(s) connected"


async def test_cancel_on_unknown_invocation_does_not_raise(bridge_daemon):
    transport = SocketTransport()
    await transport.start()
    await transport.cancel("inv_nonexistent", "test")
    await transport.close()


async def test_list_approvals_raises_not_implemented_without_a_round_trip(bridge_daemon):
    """M3 adds both sides together — until then this is a local raise, not a wire call, exactly
    matching `EmbeddedTransport`'s M1 behavior."""
    transport = SocketTransport()
    await transport.start()
    with pytest.raises(NotImplementedError):
        await transport.list_approvals()
    await transport.close()


async def test_resolve_approval_raises_not_implemented_without_a_round_trip(bridge_daemon):
    transport = SocketTransport()
    await transport.start()
    with pytest.raises(NotImplementedError):
        await transport.resolve_approval("inv_1", "approve", "once")
    await transport.close()


async def test_start_before_daemon_is_up_does_not_raise(tmp_path, monkeypatch):
    """`start()`'s eager connect must not be fatal — the first real call after the daemon comes
    up is expected to succeed via the lazy-reconnect path in `_roundtrip`."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    transport = SocketTransport()
    await transport.start()  # no daemon listening yet — must not raise
    await transport.close()


async def test_invoke_after_daemon_stops_returns_bridge_unavailable_promptly(bridge_daemon):
    tmp_path, stop_event, task = bridge_daemon
    transport = SocketTransport()
    await transport.start()

    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    req = InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id="dev_nonexistent",
        args={"payload": {}},
        deadline_ms=1000,
    )
    loop = asyncio.get_running_loop()
    start = loop.time()
    result = await transport.invoke(req)
    elapsed = loop.time() - start
    await transport.close()

    assert result.ok is False
    assert result.error["code"] == "bridge_unavailable"
    assert elapsed < 2.0
