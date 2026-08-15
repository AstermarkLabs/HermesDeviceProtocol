"""`config.py`'s path accessors — profile-scoped, read fresh on every call (ADR-0006)."""

from __future__ import annotations


def test_control_socket_path(monkeypatch, tmp_path):
    from hermes_device_plugin import config

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert config.control_socket_path() == tmp_path / "hdp" / "bridge.sock"
