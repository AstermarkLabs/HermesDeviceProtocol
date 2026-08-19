from __future__ import annotations

import hashlib
import os

import pytest
from hdp_bridge import policy


@pytest.mark.parametrize(
    ("device_id", "capability", "expected_mode", "expected_source"),
    [
        ("dev_alpha", "notifications.send", "device", "device_capability"),
        ("dev_alpha", "diagnostics.echo", "ask", "device_default"),
        ("dev_beta", "notifications.send", "ask", "global_default"),
        ("dev_beta", "clipboard.read", "deny", "fallback"),
    ],
)
def test_resolve_uses_the_documented_precedence_and_fails_closed(
    device_id, capability, expected_mode, expected_source
):
    """Removing any resolution layer or changing the fallback to allow must fail this test."""
    table = policy.PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"notifications.send": "ask"},
            "devices": {
                "dev_alpha": {
                    "default": "ask",
                    "notifications.send": "device",
                }
            },
        },
        policy_seq=7,
    )

    decision = table.resolve(device_id, capability)

    assert decision.mode.value == expected_mode
    assert decision.source == expected_source
    assert decision.policy_seq == 7


def test_default_device_is_parsed_as_target_selection_not_a_permission_layer():
    """Dropping the routing map or treating it as a mode makes this observable lookup fail."""
    table = policy.PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"notifications.send": "ask"},
            "devices": {},
            "default_device": {"notifications.send": "dev_alpha"},
        },
        policy_seq=3,
    )

    assert table.default_device_for("notifications.send") == "dev_alpha"
    assert table.default_device_for("diagnostics.echo") is None
    assert table.resolve("dev_alpha", "notifications.send").mode is policy.Mode.ASK


def test_policy_engine_validates_default_devices_against_current_non_revoked_ids(tmp_path):
    """A typo or newly revoked default must reject reload and retain the prior snapshot."""
    policy_path = tmp_path / "policy.yaml"
    known = {"dev_alpha"}
    engine = policy.PolicyEngine(policy_path, known_device_ids=lambda: set(known))
    policy_path.write_text(
        "version: 1\ndefaults:\n  notifications.send: ask\n"
        "devices: {}\ndefault_device:\n  notifications.send: dev_alpha\n"
    )
    assert engine.reload(force=True) is True
    accepted = engine.table

    known.clear()
    assert engine.reload(force=True) is False
    assert engine.table is accepted


def test_default_device_capability_must_appear_in_policy_rules():
    """A routing-only capability typo must be rejected instead of silently never matching."""
    with pytest.raises(policy.PolicyValidationError, match="does not appear in policy rules"):
        policy.PolicyTable.from_data(
            {
                "version": 1,
                "defaults": {},
                "devices": {},
                "default_device": {"notifications.send": "dev_alpha"},
            },
            policy_seq=1,
        )


def test_policy_engine_rejects_non_string_default_device_without_crashing(tmp_path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        "version: 1\ndefaults:\n  diagnostics.echo: always\n"
        "devices: {}\ndefault_device:\n  diagnostics.echo: [dev_bad]\n"
    )
    engine = policy.PolicyEngine(policy_path, known_device_ids=lambda: set())

    assert engine.reload(force=True) is False
    assert engine.table.policy_seq == 0


def test_policy_reload_audits_exact_bytes_for_accepted_and_rejected_changes(tmp_path):
    policy_path = tmp_path / "policy.yaml"
    records = []
    engine = policy.PolicyEngine(
        policy_path,
        known_device_ids=set(),
        audit=lambda event, **fields: records.append({"event": event, **fields}),
    )
    accepted_bytes = b"version: 1\ndefaults: {}\ndevices: {}\n"
    policy_path.write_bytes(accepted_bytes)

    assert engine.reload(force=True) is True
    assert records[-1] == {
        "event": "policy_changed",
        "accepted": True,
        "mtime_ns": policy_path.stat().st_mtime_ns,
        "content_sha256": hashlib.sha256(accepted_bytes).hexdigest(),
        "policy_seq": 1,
        "reason": None,
    }

    rejected_bytes = b"version: [not-valid]\n"
    policy_path.write_bytes(rejected_bytes)
    assert engine.reload(force=True) is False
    assert records[-1]["accepted"] is False
    assert records[-1]["content_sha256"] == hashlib.sha256(rejected_bytes).hexdigest()
    assert records[-1]["policy_seq"] == 1
    assert records[-1]["reason"]


def test_policy_reload_reads_candidate_bytes_once(tmp_path, monkeypatch):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("version: 1\ndefaults: {}\ndevices: {}\n")
    calls = 0
    original_open = type(policy_path).open

    class _CountingFile:
        def __init__(self, file):
            self._file = file

        def __enter__(self):
            self._file.__enter__()
            return self

        def __exit__(self, *args):
            return self._file.__exit__(*args)

        def fileno(self):
            return self._file.fileno()

        def read(self):
            nonlocal calls
            calls += 1
            return self._file.read()

    def open_counted(path, *args, **kwargs):
        return _CountingFile(original_open(path, *args, **kwargs))

    monkeypatch.setattr(type(policy_path), "open", open_counted)
    engine = policy.PolicyEngine(policy_path)

    assert engine.reload(force=True) is True
    assert calls == 1


def test_policy_reload_metadata_and_hash_share_one_atomic_file_snapshot(tmp_path, monkeypatch):
    policy_path = tmp_path / "policy.yaml"
    replacement_path = tmp_path / "policy.next.yaml"
    old_bytes = b"version: 1\ndefaults:\n  diagnostics.echo: deny\ndevices: {}\n"
    replacement_bytes = b"version: 1\ndefaults:\n  diagnostics.echo: always\ndevices: {}\n"
    policy_path.write_bytes(old_bytes)
    replacement_path.write_bytes(replacement_bytes)
    old_mtime_ns = 1_700_000_000_000_000_000
    replacement_mtime_ns = old_mtime_ns + 123_456_789
    os.utime(policy_path, ns=(old_mtime_ns, old_mtime_ns))
    os.utime(replacement_path, ns=(replacement_mtime_ns, replacement_mtime_ns))
    records = []
    original_open = type(policy_path).open
    swapped = False

    def replace_path_before_open(path, *args, **kwargs):
        nonlocal swapped
        if path == policy_path and not swapped:
            swapped = True
            os.replace(replacement_path, policy_path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(type(policy_path), "open", replace_path_before_open)
    engine = policy.PolicyEngine(
        policy_path,
        audit=lambda event, **fields: records.append({"event": event, **fields}),
    )

    assert engine.reload(force=True) is True

    assert engine.resolve("dev_1", "diagnostics.echo").mode is policy.Mode.ALWAYS
    assert records[-1]["mtime_ns"] == replacement_mtime_ns
    assert records[-1]["content_sha256"] == hashlib.sha256(replacement_bytes).hexdigest()
