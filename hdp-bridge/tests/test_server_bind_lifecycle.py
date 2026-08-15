"""`HdpServer.start()`/`close()` bind-lifecycle edge cases — specifically the two paths added
while diagnosing a `KeyError: 'HERMES_HOME'` observed during real-Hermes-install exit-gate testing
at M1 (see README.md's M1 status section): `_write_bridge_addr`'s retry-on-transient-failure, and
`close()`'s best-effort swallow of `OSError` on cleanup. Neither path is exercised by
`test_server.py` (which bypasses `HdpServer` and binds via `TestClient` directly), so both were
previously untested despite being the two concrete fixes M1's real-install testing produced.

At M2, `server.py` no longer reads any config module itself — `host`/`port`/`allow_remote`/
`bridge_addr_path` are constructor arguments (Task 4's decoupling from
`hermes_device_plugin.config`). So where the M1 version of these tests monkeypatched
`_server.config.bridge_addr_path` to simulate a flaky/always-missing path, these construct
`HdpServer` with the flaky/unwritable path directly instead.
"""

from __future__ import annotations

import pathlib

import pytest
from hdp_bridge import server as _server
from hdp_bridge.server import HdpServer, _write_bridge_addr


async def _noop_connection_factory(ws):
    raise AssertionError("no socket traffic expected in these tests")


async def test_write_bridge_addr_retries_past_transient_failure(tmp_path, monkeypatch):
    """An `OSError` on the first two attempts (simulating a transient filesystem failure) must not
    be fatal — the third attempt should succeed and the file should land."""
    addr_path = tmp_path / "hdp" / "bridge.addr"
    calls = {"n": 0}
    real_mkdir = pathlib.Path.mkdir

    def flaky_mkdir(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("simulated transient failure")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "mkdir", flaky_mkdir)

    await _write_bridge_addr(addr_path, "127.0.0.1", 8765, attempts=3, delay_s=0.0)

    assert calls["n"] == 3
    assert addr_path.read_text() == "127.0.0.1:8765\n"


async def test_write_bridge_addr_reraises_after_exhausting_attempts(tmp_path, monkeypatch):
    """If the failure is genuinely persistent (not just a transient race), the caller must still
    see it rather than have it silently swallowed — only `close()`'s best-effort cleanup path
    swallows this error, not `start()`'s."""
    addr_path = tmp_path / "hdp" / "bridge.addr"

    def always_fails(self, *args, **kwargs):
        raise OSError("simulated persistent failure")

    monkeypatch.setattr(pathlib.Path, "mkdir", always_fails)

    with pytest.raises(OSError):
        await _write_bridge_addr(addr_path, "127.0.0.1", 8765, attempts=3, delay_s=0.0)


async def test_close_swallows_oserror_from_a_missing_parent(tmp_path):
    """`HdpServer.close()` runs on the daemon thread during possibly-uncoordinated interpreter
    shutdown (D5) — a torn-down filesystem must not raise out of `close()`. No `AppRunner` was
    ever assigned here (`self._runner is None`), isolating this test to just the
    `bridge_addr_path` cleanup line. `unlink(missing_ok=True)` already suppresses the ordinary
    "file doesn't exist" case, so this uses a path whose *parent* doesn't exist either — Python's
    `unlink` still raises `FileNotFoundError` (an `OSError` subclass) walking a missing parent
    directory, exercising the `except OSError` branch rather than the `missing_ok` short-circuit.
    """
    addr_path = tmp_path / "does" / "not" / "exist" / "bridge.addr"

    server = HdpServer(
        _noop_connection_factory,
        host="127.0.0.1",
        port=0,
        allow_remote=False,
        bridge_addr_path=addr_path,
    )
    await server.close()  # must not raise


async def test_close_swallows_oserror_from_torn_down_filesystem(tmp_path):
    """Same as above but for an `OSError` raised by `unlink()` itself rather than a missing
    parent — both are documented as best-effort-only in the `close()` docstring.
    `missing_ok=True` already suppresses the ordinary "file doesn't exist" case
    (`FileNotFoundError`), so this uses a path that exists but can't be unlinked as a file
    (`unlink()` on a directory raises `IsADirectoryError`, an `OSError` subclass `missing_ok`
    does not touch) to actually exercise the `except OSError` branch rather than the
    `missing_ok` short-circuit."""
    addr_dir = tmp_path / "bridge.addr"
    addr_dir.mkdir()

    server = HdpServer(
        _noop_connection_factory,
        host="127.0.0.1",
        port=0,
        allow_remote=False,
        bridge_addr_path=addr_dir,
    )
    await server.close()  # must not raise


async def test_server_module_has_no_config_import():
    """Global Constraint: `hdp_bridge` must never import from `hermes_device_plugin` — and, more
    specifically to this module's own M2 decoupling goal, `server.py` no longer reads any config
    module of its own at all."""
    assert not hasattr(_server, "config")
