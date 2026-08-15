from __future__ import annotations

import asyncio

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

    # hdp_server.close() must have run: bridge.addr (written by hdp_server.start()) is gone,
    # and bridge.pid (which is only ever written after both binds succeed) was never created.
    assert not (tmp_path / "hdp" / "bridge.addr").exists()
    assert not (tmp_path / "hdp" / "bridge.pid").exists()
