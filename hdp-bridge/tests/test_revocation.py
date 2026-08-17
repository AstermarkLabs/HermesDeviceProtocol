"""Operator-initiated revocation (FR-15, §4.4) — the four-step order enforced in exactly this
sequence: invalidate the credential (committed first — a crash mid-revoke fails closed), send the
`revoke` wire frame, close the socket, fail every in-flight invocation for that device immediately
with a `revoked` error code (not `device_offline`)."""

from __future__ import annotations

import json

from hdp_bridge.audit import AuditWriter
from hdp_bridge.connection import NodeConnection
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import Registry
from hdp_bridge.revocation import revoke_device
from hdp_bridge.store import db


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_str(self, data):
        self.sent.append(data)

    async def close(self, *, code, message=b""):
        self.closed_with = code


async def test_revoke_invalidates_credential_sends_revoke_frame_and_fails_in_flight(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    from hdp_bridge import credentials

    credential = credentials.issue_credential(conn, "dev_1")

    registry = Registry(db_path)
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_1", capability="diagnostics.echo")
    ws = _FakeWS()
    connection = NodeConnection(
        ws,
        conn=conn,
        registry=registry,
        invocations=invocations,
        connections={"dev_1": None},
        descriptors={},
    )
    connection.device_id = "dev_1"
    connections = {"dev_1": connection}
    audit = AuditWriter(tmp_path / "audit")

    await revoke_device(conn, "dev_1", connections=connections, audit=audit)

    assert credentials.verify_credential(conn, "dev_1", credential) is False
    assert ws.closed_with is not None
    assert any('"revoke"' in frame for frame in ws.sent)
    assert entry.result_future.done()
    assert not invocations.is_pending(invocation_id)

    audit_files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    assert len(audit_files) == 1
    record = json.loads(audit_files[0].read_text().strip())
    assert record["event"] == "revoked"
    assert record["device_id"] == "dev_1"


async def test_revoke_of_unconnected_device_still_invalidates_credential(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_2', 'n', 'p', '', 0, 0, 'active')"
    )
    from hdp_bridge import credentials

    credential = credentials.issue_credential(conn, "dev_2")

    await revoke_device(conn, "dev_2", connections={})

    assert credentials.verify_credential(conn, "dev_2", credential) is False


async def test_revoke_fails_in_flight_invocation_with_revoked_not_device_offline(tmp_path):
    from hdp_bridge.invocations import DeviceDisconnected

    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_3', 'n', 'p', '', 0, 0, 'active')"
    )
    from hdp_bridge import credentials

    credentials.issue_credential(conn, "dev_3")

    registry = Registry(db_path)
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_3", capability="diagnostics.echo")
    ws = _FakeWS()
    connection = NodeConnection(
        ws,
        conn=conn,
        registry=registry,
        invocations=invocations,
        connections={"dev_3": None},
        descriptors={},
    )
    connection.device_id = "dev_3"
    connections = {"dev_3": connection}

    await revoke_device(conn, "dev_3", connections=connections)

    try:
        await entry.result_future
        raised = None
    except DeviceDisconnected as exc:
        raised = exc
    assert raised is not None
    assert raised.reason == "revoked"
