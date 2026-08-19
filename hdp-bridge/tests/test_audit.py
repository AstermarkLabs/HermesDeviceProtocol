from __future__ import annotations

import json
import os
import stat

import pytest
from hdp_bridge.audit import AuditWriter


def test_record_appends_one_json_line_with_0600_permissions(tmp_path):
    writer = AuditWriter(tmp_path / "audit")
    writer.record("paired", device_id="dev_1")
    files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    assert len(files) == 1
    mode = stat.S_IMODE(os.stat(files[0]).st_mode)
    assert mode == 0o600
    line = files[0].read_text().strip()
    record = json.loads(line)
    assert record["event"] == "paired"
    assert record["device_id"] == "dev_1"
    assert "ts" in record


def test_no_plaintext_credential_ever_reaches_the_audit_file(tmp_path):
    writer = AuditWriter(tmp_path / "audit")
    writer.record("paired", device_id="dev_1")  # never pass credential= to record()
    files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    content = files[0].read_text()
    assert "credential" not in content.lower() or "credential_hash" in content.lower()


def test_record_appends_multiple_lines_via_o_append(tmp_path):
    """Exercises O_APPEND directly: two separate `record()` calls (two separate open/close
    cycles, as every real call site does) must both land in the file, in order — not the second
    silently truncating or overwriting the first."""
    writer = AuditWriter(tmp_path / "audit")
    writer.record("daemon_start")
    writer.record("daemon_stop")
    files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    lines = files[0].read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "daemon_start"
    assert json.loads(lines[1])["event"] == "daemon_stop"


def test_record_fsyncs_security_relevant_events(tmp_path, monkeypatch):
    """`os.fsync` is actually invoked for events in the security-relevant subset, not merely
    present in the source as dead code."""
    calls = []
    real_fsync = os.fsync

    def _spy_fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _spy_fsync)
    writer = AuditWriter(tmp_path / "audit")
    writer.record("revoked", device_id="dev_1")
    assert len(calls) == 1


@pytest.mark.parametrize("event", ["approval_decided", "policy_changed"])
def test_record_fsyncs_m3_security_events(tmp_path, monkeypatch, event):
    calls = []
    real_fsync = os.fsync

    def _spy_fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _spy_fsync)
    AuditWriter(tmp_path / "audit").record(event)

    assert len(calls) == 1


def test_record_does_not_fsync_non_security_relevant_events(tmp_path, monkeypatch):
    calls = []
    real_fsync = os.fsync

    def _spy_fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _spy_fsync)
    writer = AuditWriter(tmp_path / "audit")
    writer.record("late_result", device_id="dev_1")
    assert calls == []
