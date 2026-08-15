"""`EmbeddedServer.start()`/`close()` bind-lifecycle edge cases — specifically the two paths added
while diagnosing a `KeyError: 'HERMES_HOME'` observed during real-Hermes-install exit-gate testing
(see README.md's M1 status section): `_write_bridge_addr`'s retry-on-`KeyError`, and `close()`'s
best-effort swallow of `KeyError`/`OSError` on cleanup. Neither path is exercised by
`test_transport_embedded.py` (which bypasses `EmbeddedServer` and binds via `TestClient` directly),
so both were previously untested despite being the two concrete fixes this milestone's real-install
testing produced.
"""

from __future__ import annotations

import pytest
from hermes_device_plugin.transport import _server
from hermes_device_plugin.transport._server import EmbeddedServer, _write_bridge_addr


async def _noop_connection_factory(ws):
    raise AssertionError("no socket traffic expected in these tests")


async def test_write_bridge_addr_retries_past_transient_keyerror(tmp_path, monkeypatch):
    """A `KeyError` on the first two attempts (simulating the observed `os.environ` race) must not
    be fatal — the third attempt should succeed and the file should land."""
    addr_path = tmp_path / "hdp" / "bridge.addr"
    calls = {"n": 0}

    def flaky_bridge_addr_path():
        calls["n"] += 1
        if calls["n"] < 3:
            raise KeyError("HERMES_HOME")
        return addr_path

    monkeypatch.setattr(_server.config, "bridge_addr_path", flaky_bridge_addr_path)

    await _write_bridge_addr("127.0.0.1", 8765, attempts=3, delay_s=0.0)

    assert calls["n"] == 3
    assert addr_path.read_text() == "127.0.0.1:8765\n"


async def test_write_bridge_addr_reraises_after_exhausting_attempts(monkeypatch):
    """If `HERMES_HOME` is genuinely never available (not just a transient race), the caller must
    still see the failure rather than have it silently swallowed — only `close()`'s best-effort
    cleanup path swallows this error, not `start()`'s."""

    def always_missing():
        raise KeyError("HERMES_HOME")

    monkeypatch.setattr(_server.config, "bridge_addr_path", always_missing)

    with pytest.raises(KeyError):
        await _write_bridge_addr("127.0.0.1", 8765, attempts=3, delay_s=0.0)


async def test_close_swallows_keyerror_from_missing_hermes_home(monkeypatch):
    """`EmbeddedServer.close()` runs on the daemon thread during possibly-uncoordinated interpreter
    shutdown (D5) — `config.bridge_addr_path()` reading a torn-down `os.environ` must not raise out
    of `close()`. No `AppRunner` was ever assigned here (`self._runner is None`), isolating this
    test to just the `bridge_addr_path()` cleanup line."""

    def always_missing():
        raise KeyError("HERMES_HOME")

    monkeypatch.setattr(_server.config, "bridge_addr_path", always_missing)

    server = EmbeddedServer(_noop_connection_factory)
    await server.close()  # must not raise


async def test_close_swallows_oserror_from_torn_down_filesystem(monkeypatch, tmp_path):
    """Same as above but for a genuine filesystem-level `OSError` rather than a missing env var —
    both are documented as best-effort-only in the `close()` docstring. `missing_ok=True` already
    suppresses the ordinary "file/parent doesn't exist" case (`FileNotFoundError`), so this uses a
    path that exists but can't be unlinked as a file (`unlink()` on a directory raises
    `IsADirectoryError`, an `OSError` subclass `missing_ok` does not touch) to actually exercise
    the `except (KeyError, OSError)` branch rather than the `missing_ok` short-circuit."""
    addr_dir = tmp_path / "bridge.addr"
    addr_dir.mkdir()

    monkeypatch.setattr(_server.config, "bridge_addr_path", lambda: addr_dir)

    server = EmbeddedServer(_noop_connection_factory)
    await server.close()  # must not raise
