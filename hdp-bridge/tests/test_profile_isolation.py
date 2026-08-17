# hdp-bridge/tests/test_profile_isolation.py
"""M2-6: every path resolves through config at use time. A test that imports/uses hdp_bridge
under one HERMES_HOME and then resolves under another is the fast signal a module-import-time
cache regressed this."""

from __future__ import annotations

from hdp_bridge import config
from hdp_bridge.registry import Registry


def test_two_profiles_never_share_a_registry(tmp_path, monkeypatch):
    profile_a = tmp_path / "profile-a"
    profile_b = tmp_path / "profile-b"

    monkeypatch.setenv("HERMES_HOME", str(profile_a))
    registry_a = Registry(config.registry_db_path())
    from hdp_bridge.types import DeviceRecord

    registry_a.register(
        DeviceRecord(device_id="dev_a", friendly_name="a", platform="p", online=True)
    )

    monkeypatch.setenv("HERMES_HOME", str(profile_b))
    registry_b = Registry(config.registry_db_path())
    assert registry_b.list_devices() == []
