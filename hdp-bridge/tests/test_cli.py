"""`hdp-bridge` CLI — `pair new`'s audit call site (Task 16) and `audit tail`.

No pre-existing `test_cli.py` covered `cli.py` before this task; this file's `pair new` and
`audit tail` coverage is new, not an extension of prior tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hdp_bridge import cli
from hdp_bridge.store import db as store_db
from hdp_proto.envelope import Envelope


def test_bare_hdp_launches_the_operator_tui(monkeypatch):
    launched = []
    monkeypatch.setattr(cli, "_run_tui", lambda: launched.append(True))
    monkeypatch.setattr(sys, "argv", ["hdp"])

    cli.main()

    assert launched == [True]


def test_devices_list_renders_paired_devices_from_the_daemon(monkeypatch, capsys):
    async def request(verb, payload):
        assert (verb, payload) == ("ctl_list_devices", {})
        return Envelope.new(
            "ctl_list_devices_reply",
            {
                "devices": [
                    {
                        "device_id": "dev_1",
                        "friendly_name": "desk-node",
                        "platform": "android",
                        "state": "active",
                        "online": True,
                        "capabilities": [{"name": "diagnostics.echo"}],
                    }
                ]
            },
        )

    monkeypatch.setattr("hdp_bridge.operations.control_request", request)

    cli._run_devices_list()

    output = capsys.readouterr().out
    assert "NAME" in output
    assert "PLATFORM" in output
    assert "DEVICE ID" in output
    assert "desk-node" in output
    assert "android" in output
    assert "dev_1" in output
    assert "online" in output
    assert output.lstrip()[0] != "["


def test_devices_remove_dispatches_the_existing_revoke_operation(monkeypatch):
    removed = []
    monkeypatch.setattr(cli, "_run_devices_revoke", lambda device_id: removed.append(device_id))
    monkeypatch.setattr(sys, "argv", ["hdp", "devices", "remove", "dev_1"])

    cli.main()

    assert removed == ["dev_1"]


def test_approvals_list_renders_daemon_held_pending_records(monkeypatch, capsys):
    async def request(verb, payload):
        assert (verb, payload) == ("ctl_list_approvals", {})
        return Envelope.new(
            "ctl_list_approvals_reply",
            {
                "approvals": [
                    {
                        "invocation_id": "inv_1",
                        "device_id": "dev_1",
                        "capability": "diagnostics.echo",
                        "version": 2,
                    }
                ]
            },
        )

    monkeypatch.setattr("hdp_bridge.operations.control_request", request)

    cli._run_approvals_list()

    assert json.loads(capsys.readouterr().out) == [
        {
            "invocation_id": "inv_1",
            "device_id": "dev_1",
            "capability": "diagnostics.echo",
            "version": 2,
        }
    ]


@pytest.mark.parametrize(("decision", "scope"), [("approve", "session"), ("deny", "one_time")])
def test_approval_decisions_use_the_control_plane(monkeypatch, capsys, decision: str, scope: str):
    async def request(verb, payload):
        assert verb == "ctl_resolve_approval"
        assert payload == {
            "invocation_id": "inv_1",
            "decision": decision,
            "scope": scope,
        }
        return Envelope.new("ctl_resolve_approval_reply", {"ok": True, "state": f"{decision}d"})

    monkeypatch.setattr("hdp_bridge.operations.control_request", request)

    cli._run_approval_resolve("inv_1", decision=decision, scope=scope)

    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_policy_show_and_reload_are_read_only_control_plane_clients(monkeypatch, capsys):
    replies = {
        "ctl_policy_show": Envelope.new("ctl_policy_show_reply", {"policy_seq": 4, "defaults": {}}),
        "ctl_policy_reload": Envelope.new("ctl_policy_reload_reply", {"ok": True, "policy_seq": 5}),
    }

    async def request(verb, payload):
        assert payload == {}
        return replies[verb]

    monkeypatch.setattr("hdp_bridge.operations.control_request", request)

    cli._run_policy_control("show")
    cli._run_policy_control("reload")

    rendered = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rendered == [
        {"defaults": {}, "policy_seq": 4},
        {"ok": True, "policy_seq": 5},
    ]


def test_policy_validate_checks_a_file_without_replacing_daemon_policy(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store_db.connect(tmp_path / "hdp" / "registry.db")
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text("version: 1\ndefaults: {}\ndevices: {}\ndefault_device: {}\n")

    cli._run_policy_validate(Path(candidate))

    assert json.loads(capsys.readouterr().out) == {"ok": True, "policy_seq": 1}


def test_pair_new_is_rejected_without_minting_a_code(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store_db.connect(tmp_path / "hdp" / "registry.db")

    with pytest.raises(SystemExit, match="2"):
        cli._run_pair_new()

    assert "pairing codes are disabled" in capsys.readouterr().err
    assert not list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))


def test_audit_tail_prints_todays_audit_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hdp_bridge.audit import AuditWriter

    audit_dir = tmp_path / "hdp" / "audit"
    AuditWriter(audit_dir).record("daemon_start")

    cli._run_audit_tail()

    out = capsys.readouterr().out
    assert json.loads(out.strip())["event"] == "daemon_start"


def test_audit_tail_prints_nothing_when_no_audit_file_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    cli._run_audit_tail()

    assert capsys.readouterr().out == ""


def test_devices_revoke_offline_fallback_records_a_revoked_audit_entry(
    tmp_path, monkeypatch, capsys
):
    """Task 17's gap-fix for the review finding carried forward from Task 16: with no daemon
    reachable, `_run_devices_revoke` used to invalidate the credential via
    `credentials.revoke_credential` directly (bypassing `revocation.revoke_device`) and leave zero
    audit trail. It must now record its own `revoked` event, distinguishable from the live-daemon
    path by `via="offline_fallback"`."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # No control socket bound at $HERMES_HOME/hdp/bridge.sock — `_via_control_socket` fails to
    # connect and `_run_devices_revoke` falls through to the DB-only branch under test.
    conn = store_db.connect(tmp_path / "hdp" / "registry.db")
    # A real device + live credential: as of finding I4's fix, revoking a device_id with no live
    # credential is a reported no-op, not a silent success, so this test has to revoke something
    # that actually exists for the audit record it asserts on to be produced at all.
    _insert_device_with_credential(conn, "dev_1")

    cli._run_devices_revoke("dev_1")

    assert capsys.readouterr().out.strip() == "revoked dev_1"
    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "revoked"
    assert record["device_id"] == "dev_1"
    assert record["via"] == "offline_fallback"


def _insert_device_with_credential(conn, device_id: str) -> None:
    """A minimal `devices` row plus one live `credentials` row — the smallest state in which a
    revoke has something real to invalidate."""
    from hdp_bridge import credentials

    with conn:
        conn.execute(
            "INSERT INTO devices (device_id, friendly_name, platform, first_paired_at, "
            "last_seen_at) VALUES (?, ?, ?, 0, 0)",
            (device_id, "test-node", "linux"),
        )
    credentials.issue_credential(conn, device_id)


def test_devices_revoke_of_an_unknown_device_reports_no_such_device_and_audits_nothing(
    tmp_path, monkeypatch, capsys
):
    """Finding I4: the offline fallback used to print "revoked <id>" unconditionally, even when
    the UPDATE touched zero rows. An operator typo now says so, and no `revoked` audit record is
    written for a revocation that did not happen. Round 2 of I4: the process also exits non-zero,
    so a caller scripting `hdp devices revoke $id && next-step` can't proceed past this."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store_db.connect(tmp_path / "hdp" / "registry.db")

    with pytest.raises(SystemExit) as exc_info:
        cli._run_devices_revoke("dev_nonexistent")

    assert exc_info.value.code == 1
    assert capsys.readouterr().out.strip() == "no such device dev_nonexistent"
    assert not list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))


def test_devices_revoke_twice_reports_no_such_device_the_second_time(tmp_path, monkeypatch, capsys):
    """Already-revoked is the same zero-rows case as never-existed — both are "nothing happened"
    and neither earns a second audit record."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    conn = store_db.connect(tmp_path / "hdp" / "registry.db")
    _insert_device_with_credential(conn, "dev_1")

    cli._run_devices_revoke("dev_1")
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc_info:
        cli._run_devices_revoke("dev_1")

    assert exc_info.value.code == 1
    assert capsys.readouterr().out.strip() == "no such device dev_1"
    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    assert len(audit_files[0].read_text().strip().splitlines()) == 1
