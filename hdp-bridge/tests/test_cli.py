"""`hdp-bridge` CLI — `pair new`'s audit call site (Task 16) and `audit tail`.

No pre-existing `test_cli.py` covered `cli.py` before this task; this file's `pair new` and
`audit tail` coverage is new, not an extension of prior tests.
"""

from __future__ import annotations

import json

from hdp_bridge import cli
from hdp_bridge.store import db as store_db


def test_pair_new_records_pairing_code_minted_with_no_code_or_hash(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # `_run_pair_new` connects to the registry DB directly (no daemon needed for this path) —
    # touch it via the same helper the CLI uses so the schema exists first.
    store_db.connect(tmp_path / "hdp" / "registry.db")

    cli._run_pair_new()

    printed_code = capsys.readouterr().out.strip()
    assert printed_code  # the plaintext code still goes to stdout, exactly once

    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "pairing_code_minted"
    # No code, no hash — literally nothing about *which* code (no-plaintext rule).
    assert printed_code not in json.dumps(record)
    assert set(record.keys()) == {"event", "ts"}


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
    store_db.connect(tmp_path / "hdp" / "registry.db")

    cli._run_devices_revoke("dev_1")

    assert capsys.readouterr().out.strip() == "revoked dev_1"
    audit_files = list((tmp_path / "hdp" / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "revoked"
    assert record["device_id"] == "dev_1"
    assert record["via"] == "offline_fallback"
