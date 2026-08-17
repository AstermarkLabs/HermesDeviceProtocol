"""`hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`, not
`test_cli.py`, because `hdp-bridge/tests/test_cli.py` already claims that basename and both
`tests/` dirs are on `testpaths` with no `__init__.py` — pytest's default (prepend) import mode
would collide on two same-named top-level modules otherwise (mirrors why `hdp-bridge` named its
config test `test_bridge_config.py`).

Two levels of coverage: unreachable-daemon behavior needs no fixture at all (no socket bound);
`status`/`devices` against a real, running device need a real `hdp_bridge.daemon.serve()` task,
same pattern as `test_transport_socket.py`'s `bridge_daemon` fixture.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from hermes_device_plugin import cli


@pytest.fixture
async def bridge_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    from hdp_bridge import daemon

    stop_event = asyncio.Event()
    task = asyncio.create_task(daemon.serve(stop_event=stop_event))
    await asyncio.sleep(0.2)
    yield tmp_path
    if not stop_event.is_set():
        stop_event.set()
        await asyncio.wait_for(task, timeout=5)


def _register_device(tmp_path, **overrides):
    from hdp_bridge.config import registry_db_path
    from hdp_bridge.registry import Registry
    from hdp_bridge.types import DeviceRecord

    fields = {
        "device_id": "dev_1",
        "friendly_name": "Living Room",
        "platform": "android",
        "online": False,
        "state": "active",
    }
    fields.update(overrides)
    Registry(registry_db_path()).register(DeviceRecord(**fields))


async def test_render_status_reports_unreachable_with_no_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")

    out = await cli.render_status()

    assert "unreachable" in out


async def test_render_devices_reports_unreachable_with_no_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")

    out = await cli.render_devices()

    assert "cannot reach hdp-bridge daemon" in out


async def test_render_status_reports_healthy_against_a_real_daemon(bridge_daemon):
    out = await cli.render_status()
    assert "healthy" in out


async def test_render_devices_contains_device_id_and_state_against_a_real_daemon(bridge_daemon):
    tmp_path = bridge_daemon
    _register_device(tmp_path, device_id="dev_42", friendly_name="Kitchen", state="active")

    out = await cli.render_devices()

    assert "dev_42" in out
    assert "active" in out


async def test_render_devices_reports_no_paired_devices_when_daemon_has_none(bridge_daemon):
    out = await cli.render_devices()
    assert out == "no paired devices"


async def test_render_pair_new_mints_a_code_and_records_no_plaintext_audit_entry(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hdp_bridge.config import registry_db_path
    from hdp_bridge.store import db as store_db

    store_db.connect(registry_db_path())  # ensure schema exists, same as hdp-bridge's own test

    code = await cli.render_pair_new()

    assert code  # a plaintext code is returned, exactly once
    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "pairing_code_minted"
    assert code not in json.dumps(record)  # no-plaintext rule


async def test_render_devices_revoke_offline_fallback_records_via_marker(tmp_path, monkeypatch):
    """No daemon reachable — `render_devices_revoke` falls back to the direct DB-only revoke and
    must record its own `revoked` audit entry with `via="offline_fallback"` (Task 16's gap,
    closed here the same way it's closed in `hdp_bridge/cli.py`)."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    from hdp_bridge import credentials
    from hdp_bridge.config import registry_db_path
    from hdp_bridge.store import db as store_db

    conn = store_db.connect(registry_db_path())
    # A real device + live credential: as of finding I4's fix, revoking a device_id with no live
    # credential is a reported no-op, so this test must revoke something that actually exists.
    _register_device(tmp_path, device_id="dev_1")
    credentials.issue_credential(conn, "dev_1")

    out = await cli.render_devices_revoke("dev_1")

    assert out == "revoked dev_1"
    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "revoked"
    assert record["device_id"] == "dev_1"
    assert record["via"] == "offline_fallback"


async def test_render_devices_revoke_against_a_real_daemon_reaches_the_control_socket(
    bridge_daemon,
):
    tmp_path = bridge_daemon
    _register_device(tmp_path, device_id="dev_1")
    from hdp_bridge.config import registry_db_path
    from hdp_bridge.store import db as store_db

    conn = store_db.connect(registry_db_path())
    from hdp_bridge import credentials

    credentials.issue_credential(conn, "dev_1")

    out = await cli.render_devices_revoke("dev_1")

    assert out == "revoked dev_1"
    # No offline-fallback marker on the live-daemon path — that record shape belongs to
    # `revocation.revoke_device` (control.py's `_ctl_devices_revoke`), not this CLI's fallback.
    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    events = [
        json.loads(line) for f in audit_files for line in f.read_text().splitlines() if line.strip()
    ]
    revoked = [e for e in events if e["event"] == "revoked"]
    assert len(revoked) == 1
    assert "via" not in revoked[0]


async def test_render_devices_revoke_of_an_unknown_device_reports_no_such_device(
    tmp_path, monkeypatch
):
    """Finding I4, offline-fallback half: no live credential means nothing was revoked. Say so,
    and write no audit record for a revocation that did not happen."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    from hdp_bridge.config import registry_db_path
    from hdp_bridge.store import db as store_db

    store_db.connect(registry_db_path())

    out = await cli.render_devices_revoke("dev_nope")

    assert out == "no such device dev_nope"
    assert not list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))


async def test_render_devices_revoke_surfaces_a_daemon_error_instead_of_reporting_success(
    bridge_daemon,
):
    """Finding I4, live-daemon half: both CLIs used to `await read_frame(...)` and throw the reply
    away, then print "revoked <id>" unconditionally — a fail-open report of an operation the
    daemon had actually refused. The reply's type is now checked, and an `error` envelope is
    surfaced."""
    out = await cli.render_devices_revoke("dev_never_paired")

    assert out.startswith("revoke failed:")
    assert "no_matching_device" in out


async def test_render_audit_reports_unreachable_with_no_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")

    out = await cli.render_audit()

    assert "cannot reach hdp-bridge daemon" in out


async def test_render_audit_against_a_real_daemon_contains_daemon_start(bridge_daemon):
    out = await cli.render_audit()
    assert "daemon_start" in out


def test_register_cli_command_registers_hdp():
    calls = []

    class _Ctx:
        def register_cli_command(self, **kwargs):
            calls.append(kwargs)

    cli.register_cli_command(_Ctx())

    assert len(calls) == 1
    assert calls[0]["name"] == "hdp"
    assert calls[0]["handler"] is cli.main
