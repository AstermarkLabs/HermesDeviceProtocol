from __future__ import annotations

import asyncio

from hdp_bridge import daemon


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
