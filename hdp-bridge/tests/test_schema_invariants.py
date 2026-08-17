"""NFR-6 and FR-37, enforced against the live post-migration database, not the .sql text (same
discipline as hdp-spec/tests/test_errors_conformance.py's errors.py <-> errors.md parity check)."""

from __future__ import annotations

from hdp_bridge.store import db

_FORBIDDEN_COLUMN_SUBSTRINGS = ("message", "conversation", "content", "transcript")


def test_no_table_has_a_conversation_or_message_column(tmp_path):
    """NFR-6: registry.db is not a second Hermes session database."""
    conn = db.connect(tmp_path / "registry.db")
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_version'"
        )
    ]
    assert tables, "expected at least the seven state tables to exist"
    for table in tables:
        columns = {r[1].lower() for r in conn.execute(f"PRAGMA table_info({table})")}
        for forbidden in _FORBIDDEN_COLUMN_SUBSTRINGS:
            matches = {c for c in columns if forbidden in c}
            assert not matches, f"table {table!r} has forbidden column(s) {matches} (NFR-6)"


def test_invocations_table_has_no_argument_or_result_column(tmp_path):
    """FR-37: full arguments live only in the audit log, never in the registry."""
    conn = db.connect(tmp_path / "registry.db")
    columns = {r[1].lower() for r in conn.execute("PRAGMA table_info(invocations)")}
    for forbidden in ("args", "arguments", "result", "data", "payload"):
        assert forbidden not in columns, f"invocations.{forbidden} violates FR-37"


def test_approvals_table_has_no_raw_argument_column_only_a_summary(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    columns = {r[1].lower() for r in conn.execute("PRAGMA table_info(approvals)")}
    assert "args_summary" in columns
    for forbidden in ("args", "arguments", "raw_args"):
        assert forbidden not in columns
