"""Test-wide fixtures for `hermes_device_plugin`.

Real Hermes always sets `$HERMES_HOME` before loading any plugin (ADR-0006) — every test here
runs under that same assumption via an autouse fixture, rather than `config.py` special-casing an
unset value. M1's production transport, `EmbeddedTransport`, writes a `bridge.addr` discovery
file under `$HERMES_HOME/hdp/` on `start()` (see `transport/_server.py`), so any test that builds
a real `HDPRuntime` — which now defaults to `EmbeddedTransport`, not the M0 loopback stub — needs
a real, if temporary, directory to write it into. `HDP_BIND_PORT=0` requests an OS-assigned
ephemeral port so parallel test runs never fight over a fixed one.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    yield tmp_path
