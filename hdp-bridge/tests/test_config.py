from __future__ import annotations

from hdp_bridge import config


def test_paths_are_profile_scoped(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert config.hdp_home() == tmp_path / "hdp"
    assert config.control_socket_path() == tmp_path / "hdp" / "bridge.sock"
    assert config.pid_path() == tmp_path / "hdp" / "bridge.pid"
    assert config.bridge_addr_path() == tmp_path / "hdp" / "bridge.addr"


def test_paths_read_home_fresh_every_call(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "a"))
    first = config.hdp_home()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "b"))
    second = config.hdp_home()
    assert first != second
