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
import json

import pytest
from hdp_proto.envelope import Envelope
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


# -- multiplexing (final-review finding I3) ----------------------------------------------------


class _FakeControlServer:
    """A minimal stand-in for `hdp_bridge.control.ControlServer`, speaking the same framing.

    `SocketTransport`'s multiplexing can't be proven against the `bridge_daemon` fixture above:
    with zero devices connected, `ctl_invoke` returns `device_offline` instantly, so there is
    nothing to overlap. This server instead answers `ctl_invoke` after a controlled delay (off
    its own read loop, exactly as the real one does) and everything else immediately — which
    makes the timing deterministic and needs no node subprocesses.
    """

    def __init__(self, socket_path, *, invoke_delay_s: float) -> None:
        self._socket_path = socket_path
        self._invoke_delay_s = invoke_delay_s
        self._server = None
        self._tasks: set[asyncio.Task] = set()
        self._writers: set[asyncio.StreamWriter] = set()
        self.concurrent_invokes = 0
        self.max_concurrent_invokes = 0

    async def start(self) -> None:
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = await asyncio.start_unix_server(self._handle, str(self._socket_path))

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        # `Server.close()` only stops *listening*; already-accepted connections survive it, so a
        # client would never see EOF. Force-close them, the same way the real `ControlServer`
        # does — "a stopped daemon is actually stopped, not merely deaf".
        for writer in list(self._writers):
            writer.close()
        self._writers.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader, writer) -> None:
        self._writers.add(writer)
        while True:
            try:
                header = await reader.readexactly(4)
                body = await reader.readexactly(int.from_bytes(header, "big"))
            except asyncio.IncompleteReadError:
                return
            envelope = Envelope.from_wire(json.loads(body))
            if envelope.type == "ctl_invoke":
                task = asyncio.ensure_future(self._reply_slowly(envelope, writer))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                continue
            self._write(
                writer, Envelope.new("ctl_status_reply", {"healthy": True}, corr=envelope.id)
            )

    async def _reply_slowly(self, envelope, writer) -> None:
        self.concurrent_invokes += 1
        self.max_concurrent_invokes = max(self.max_concurrent_invokes, self.concurrent_invokes)
        try:
            await asyncio.sleep(self._invoke_delay_s)
            reply = Envelope.new(
                "ctl_invoke_reply",
                {"invocation_id": envelope.id, "ok": True, "data": {"payload": {}}},
                corr=envelope.id,
            )
            self._write(writer, reply)
        finally:
            self.concurrent_invokes -= 1

    @staticmethod
    def _write(writer, envelope) -> None:
        body = json.dumps(envelope.to_wire()).encode("utf-8")
        writer.write(len(body).to_bytes(4, "big") + body)


@pytest.fixture
async def fake_control_server(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_device_plugin import config

    server = _FakeControlServer(config.control_socket_path(), invoke_delay_s=1.0)
    await server.start()
    try:
        yield server
    finally:
        await server.close()


def _invoke_request(device_id: str) -> InvokeRequest:
    return InvokeRequest(
        capability="diagnostics.echo",
        version=1,
        device_id=device_id,
        args={"payload": {}},
        deadline_ms=10_000,
    )


async def test_two_concurrent_invocations_overlap_instead_of_queueing(fake_control_server):
    """Finding I3, client half: `_roundtrip` used to hold one lock across both the write and the
    read of the control socket, so a second `invoke()` could not even send its frame until the
    first had its reply — every device invocation in the plugin process serialised behind
    whichever one was in flight.

    Two invocations against two different devices, each taking ~1s server-side. Serialised, the
    pair takes ~2s; multiplexed, ~1s. Banded well below the serial figure so the regression fails
    it without a loaded machine flaking it."""
    transport = SocketTransport()
    await transport.start()
    try:
        loop = asyncio.get_running_loop()
        start = loop.time()
        first, second = await asyncio.gather(
            transport.invoke(_invoke_request("dev_a")),
            transport.invoke(_invoke_request("dev_b")),
        )
        elapsed = loop.time() - start
    finally:
        await transport.close()

    assert first.ok is True
    assert second.ok is True
    assert first.invocation_id != second.invocation_id, "replies were mismatched by the demux"
    assert fake_control_server.max_concurrent_invokes == 2
    assert elapsed < 1.6, f"invocations serialised ({elapsed:.2f}s for two ~1s calls)"


async def test_a_status_call_is_not_blocked_by_an_in_flight_invocation(fake_control_server):
    """The corollary: any other call — `cancel()` included, which is why this deadlock mattered
    even before it had a production caller — must interleave with an outstanding invocation."""
    transport = SocketTransport()
    await transport.start()
    try:
        invoke_task = asyncio.ensure_future(transport.invoke(_invoke_request("dev_a")))
        await asyncio.sleep(0.1)  # let the invoke frame go out and stall server-side

        loop = asyncio.get_running_loop()
        start = loop.time()
        status = await transport.status()
        elapsed = loop.time() - start

        assert status.healthy is True
        assert elapsed < 0.5, f"status waited on the in-flight invoke ({elapsed:.2f}s)"
        assert (await invoke_task).ok is True
    finally:
        await transport.close()


async def test_pending_calls_are_released_when_the_daemon_disappears_mid_flight(
    fake_control_server,
):
    """A future parked on a reply the connection can no longer deliver must be failed, not left
    hanging — the failure mode the per-connection `_pending` dict and `_read_loop`'s `finally`
    exist to prevent."""
    transport = SocketTransport()
    await transport.start()
    try:
        invoke_task = asyncio.ensure_future(transport.invoke(_invoke_request("dev_a")))
        await asyncio.sleep(0.1)
        await fake_control_server.close()

        result = await asyncio.wait_for(invoke_task, timeout=5)
    finally:
        await transport.close()

    assert result.ok is False
    assert result.error["code"] == "bridge_unavailable"
