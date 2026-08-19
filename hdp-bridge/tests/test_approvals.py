from __future__ import annotations

from hdp_bridge import approvals
from hdp_bridge.store import db


def test_expiring_an_unresolved_approval_writes_one_terminal_row(tmp_path):
    """Persisting pending approvals or expiring before 120 seconds must fail this test."""
    conn = db.connect(tmp_path / "registry.db")
    manager = approvals.ApprovalManager(conn, timeout_s=120)
    pending = manager.create(
        invocation_id="inv_1",
        device_id="dev_1",
        capability="notifications.send",
        version=1,
        args_summary="title='hello'",
        requesting_session="session_1",
        risk_class="",
        now=1_000,
    )

    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    assert manager.expire_pending(now=1_119) == []

    outcomes = manager.expire_pending(now=1_120)

    assert [(outcome.state.value, outcome.pending.invocation_id) for outcome in outcomes] == [
        ("expired", "inv_1")
    ]
    row = conn.execute(
        "SELECT state, decided_by, scope FROM approvals WHERE invocation_id = ?",
        (pending.invocation_id,),
    ).fetchone()
    assert tuple(row) == ("expired", None, None)
    assert manager.list_pending() == []


def test_session_decision_is_memory_only_and_persistent_decision_creates_grant(tmp_path):
    """Writing a session grant to SQLite or omitting a persistent grant must fail this test."""
    conn = db.connect(tmp_path / "registry.db")
    manager = approvals.ApprovalManager(conn)
    session = manager.create(
        invocation_id="inv_session",
        device_id="dev_1",
        capability="notifications.send",
        version=1,
        args_summary="",
        requesting_session="session_1",
        risk_class="",
        now=0,
    )
    manager.resolve(session.invocation_id, approved=True, scope="session", decided_by="cli", now=1)

    assert manager.has_session_grant("session_1", "dev_1", "notifications.send") is True
    assert conn.execute("SELECT COUNT(*) FROM policy_grants").fetchone()[0] == 0

    persistent = manager.create(
        invocation_id="inv_persistent",
        device_id="dev_1",
        capability="notifications.send",
        version=1,
        args_summary="",
        requesting_session="session_1",
        risk_class="",
        now=2,
    )
    manager.resolve(
        persistent.invocation_id, approved=True, scope="persistent", decided_by="cli", now=3
    )

    row = conn.execute("SELECT mode, scope FROM policy_grants").fetchone()
    assert tuple(row) == ("always", "persistent")
