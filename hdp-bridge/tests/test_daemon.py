from __future__ import annotations

import asyncio
import os

import pytest
from hdp_bridge import daemon
from hdp_bridge.control import ControlServer


async def test_serve_binds_control_socket_and_writes_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    stop_event = asyncio.Event()
    serve_task = asyncio.create_task(daemon.serve(stop_event=stop_event))
    await asyncio.sleep(0.2)  # let bind complete
    assert (tmp_path / "hdp" / "bridge.sock").exists()
    assert (tmp_path / "hdp" / "bridge.pid").exists()
    assert (tmp_path / "hdp" / "bridge.addr").exists()
    stop_event.set()
    await asyncio.wait_for(serve_task, timeout=5)
    assert not (tmp_path / "hdp" / "bridge.sock").exists()
    assert not (tmp_path / "hdp" / "bridge.pid").exists()


async def test_serve_tears_down_node_socket_if_control_bind_fails(tmp_path, monkeypatch):
    """A partial-bind failure (`hdp_server.start()` succeeds, `control.start()` raises) must
    not leak the already-bound node-facing TCP socket or the `bridge.addr` file it wrote."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")

    async def _boom(self):
        raise RuntimeError("control socket bind failed")

    monkeypatch.setattr(ControlServer, "start", _boom)

    with pytest.raises(RuntimeError, match="control socket bind failed"):
        await daemon.serve()

    # hdp_server.close() must have run: bridge.addr (written by hdp_server.start()) is gone.
    # bridge.pid is claimed before either socket binds (Task 15), so it did briefly exist —
    # but the failure path must unclaim it, since no daemon is actually left running.
    assert not (tmp_path / "hdp" / "bridge.addr").exists()
    assert not (tmp_path / "hdp" / "bridge.pid").exists()


async def test_serve_refuses_to_start_when_a_live_process_holds_the_pid_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pid_path = tmp_path / "hdp" / "bridge.pid"
    pid_path.parent.mkdir(parents=True)
    pid_path.write_text(str(os.getpid()))  # this test process is definitely alive

    with pytest.raises(daemon.AlreadyRunningError):
        await daemon.serve(stop_event=asyncio.Event())


async def test_serve_cleans_up_a_stale_pid_from_a_dead_process(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    pid_path = tmp_path / "hdp" / "bridge.pid"
    pid_path.parent.mkdir(parents=True)
    pid_path.write_text("999999999")  # not a real PID

    stop_event = asyncio.Event()
    task = asyncio.create_task(daemon.serve(stop_event=stop_event))
    await asyncio.sleep(0.2)
    assert pid_path.read_text().strip() != "999999999"  # overwritten with our own PID
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)
