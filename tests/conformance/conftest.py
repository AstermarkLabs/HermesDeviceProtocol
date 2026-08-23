"""Shared fixtures for the M2 conformance suite (m1-plan.md §7, m2-plan.md).

HDP now runs as three real, separate OS processes in this suite: the test process (driving a
`SocketTransport`), a real `hdp-bridge serve` subprocess (bound to an OS-assigned ephemeral TCP
port for nodes and a Unix control socket for the plugin side), and — where a fault needs a real
uncooperative peer — a real `hdp-node` CLI subprocess. This proves the failure paths hold over
actual sockets between separate OS processes (m1-plan.md's header risk statement), not an
in-process function call standing in for one.
"""

from __future__ import annotations

import asyncio
import contextlib
import os

import pytest
from harness import start_bridge, stop_bridge
from hermes_device_plugin import config
from hermes_device_plugin.transport.socket import SocketTransport


def external_node_mode() -> bool:
    """Is the suite being pointed at a real, externally-connected node (M6)?

    In that mode the peer is a physical or emulated device pairing against the operator's own
    running bridge, so the suite must not commandeer `$HERMES_HOME` or start a daemon of its own —
    it attaches to what is already there. Every assertion downstream is unchanged; only the
    fixture wiring differs, which is the point of M5's "runnable against an Android endpoint
    without changing its assertions" gate.
    """
    return os.environ.get("HDP_EXTERNAL_NODE") == "1"


@pytest.fixture(autouse=True)
def _hermes_home(tmp_path, monkeypatch):
    if external_node_mode():
        # Use the operator's real profile — the device is paired against that bridge, not a
        # throwaway one this process would own.
        yield None
        return
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    yield tmp_path


@pytest.fixture
async def _bridge_proc(_hermes_home):
    if external_node_mode():
        # The operator's bridge is already serving; adopt it rather than starting a second one,
        # which would fail the PID claim anyway.
        yield None, []
        return
    async for value in _managed_bridge_proc(_hermes_home):
        yield value


async def _managed_bridge_proc(_hermes_home):
    """Starts the real `hdp-bridge serve` subprocess and continuously drains its stdout (stderr
    is redirected into it, per `start_bridge`) into `lines` as it's produced. `hdp-bridge serve`
    runs with `logging.basicConfig(level=INFO, ...)` (`daemon.main`), so bridge-side log records
    like `late_result`/`schema_drift` land here — they're emitted inside the daemon subprocess,
    not the test process, so `caplog` (which only captures the test process's own logging) can't
    see them. `bridge_log` (below) is the replacement: it reads this same continuously-updated
    list, the subprocess equivalent of `caplog.text`."""
    proc = await start_bridge(_hermes_home)
    lines: list[str] = []

    async def _drain() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            lines.append(raw.decode(errors="replace"))

    drain_task = asyncio.create_task(_drain())
    try:
        yield proc, lines
    finally:
        await stop_bridge(proc)
        # `stop_bridge` has already terminated the process, so its stdout will hit EOF shortly —
        # let `_drain` finish reading whatever was already flushed before the pipe closed, rather
        # than cancelling it and possibly losing the last few buffered lines.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(drain_task, timeout=5)
        if not drain_task.done():
            drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await drain_task


@pytest.fixture
async def bridge(_bridge_proc):
    # `_hermes_home` (autouse, consumed transitively by `_bridge_proc`) has already set
    # $HERMES_HOME to a fresh `tmp_path` for this test — `start_bridge` launches the daemon
    # against it, and `SocketTransport` below reads the same env var fresh at construction time
    # (ADR-0006), so both sides agree on one temp directory.
    transport = SocketTransport()
    await transport.start()
    try:
        yield transport
    finally:
        await transport.close()


@pytest.fixture
def bridge_log(_bridge_proc):
    """The bridge subprocess's captured stdout/stderr lines so far, live-updated as the daemon
    logs — the subprocess-log equivalent of `caplog.text` for tests that need to observe
    bridge-side-only log records (`late_result`, `schema_drift`, ...)."""
    _proc, lines = _bridge_proc
    return lines


@pytest.fixture
def bridge_url(bridge):
    host_port = config.bridge_addr_path().read_text().strip()
    return f"ws://{host_port}/hdp/v0/socket"
