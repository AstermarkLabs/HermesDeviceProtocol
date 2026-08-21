from __future__ import annotations

import asyncio

import pytest
from hdp_bridge import approvals
from hdp_bridge.store import db


def test_abandon_removes_pending_approval_without_persisting_a_decision(tmp_path):
    """A disconnected device cannot leave an unresolvable approval in the operator queue."""
    conn = db.connect(tmp_path / "registry.db")
    manager = approvals.ApprovalManager(conn)
    manager.create(
        invocation_id="inv_abandoned",
        device_id="dev_1",
        capability="diagnostics.echo",
        version=1,
        args_summary="(0 fields)",
        requesting_session=None,
        risk_class="",
    )

    assert manager.abandon("inv_abandoned") is True
    assert manager.list_pending() == []
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM approvals WHERE invocation_id = 'inv_abandoned'"
        ).fetchone()[0]
        == 0
    )


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


async def test_invalid_scope_does_not_consume_pending_approval_or_waiter(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    manager = approvals.ApprovalManager(conn)
    manager.create(
        invocation_id="inv_1",
        device_id="dev_1",
        capability="notifications.send",
        version=1,
        args_summary="",
        requesting_session="session_1",
        risk_class="",
    )
    waiter = asyncio.create_task(manager.wait("inv_1"))
    await asyncio.sleep(0)

    with pytest.raises(ValueError):
        manager.resolve("inv_1", approved=True, scope="invalid", decided_by="cli")

    assert [pending.invocation_id for pending in manager.list_pending()] == ["inv_1"]
    resolution = manager.resolve("inv_1", approved=True, scope="one_time", decided_by="cli")
    assert (await waiter) is resolution
