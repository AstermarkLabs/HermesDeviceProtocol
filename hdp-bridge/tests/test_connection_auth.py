"""`_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired connections at
all. A `hello` presenting no credential, or one that resolves to no live credential, gets
`auth_failed` and the connection closes — there is no more anonymous/unpaired path. A first-time
pairing is carried through the same `credential` field, prefixed `pair:`, distinguishing "this is
a pairing code" from "this is a returning device's credential" without a wire-shape change.

Uses a fake WebSocketResponse double (`send_str` records frames, `close` records the code) so
these tests don't need a real aiohttp server — `NodeConnection`'s methods are exercised directly.
"""

from __future__ import annotations

import json

from hdp_bridge import credentials, pairing
from hdp_bridge.audit import AuditWriter
from hdp_bridge.connection import NodeConnection
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import Registry
from hdp_bridge.store import db
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Hello, Welcome


def _read_audit_records(audit_dir):
    files = list(audit_dir.glob("audit-*.jsonl"))
    assert len(files) == 1
    return [json.loads(line) for line in files[0].read_text().splitlines()]


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_str(self, data):
        self.sent.append(data)

    async def close(self, *, code, message=b""):
        self.closed_with = code

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


async def test_hello_with_no_credential_is_auth_failed(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    registry = Registry(tmp_path / "registry.db")
    ws = _FakeWS()
    audit = AuditWriter(tmp_path / "audit")
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={},
        descriptors={}, audit=audit,
    )

    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=None)
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert ws.closed_with is not None
    assert connection.device_id is None

    records = _read_audit_records(tmp_path / "audit")
    assert records[-1] == {
        "event": "auth_failed", "ts": records[-1]["ts"], "reason": "no_credential",
    }


async def test_hello_with_an_unknown_credential_is_auth_failed(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    registry = Registry(tmp_path / "registry.db")
    ws = _FakeWS()
    audit = AuditWriter(tmp_path / "audit")
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={},
        descriptors={}, audit=audit,
    )

    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential="bogus")
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert ws.closed_with is not None
    assert connection.device_id is None

    records = _read_audit_records(tmp_path / "audit")
    assert records[-1]["event"] == "auth_failed"
    assert records[-1]["reason"] == "unknown_credential"


async def test_hello_with_an_invalid_pairing_code_is_auth_failed(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    registry = Registry(tmp_path / "registry.db")
    ws = _FakeWS()
    audit = AuditWriter(tmp_path / "audit")
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={},
        descriptors={}, audit=audit,
    )

    hello = Hello(
        hdp_versions=(0,), device_name="n", capabilities=(), credential="pair:NOT-A-REAL-CODE"
    )
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert ws.closed_with is not None
    assert connection.device_id is None

    records = _read_audit_records(tmp_path / "audit")
    assert records[-1]["event"] == "auth_failed"
    assert records[-1]["reason"] == "invalid_or_expired_pairing_code"


async def test_hello_with_a_valid_pairing_code_pairs_and_returns_a_credential(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    code = pairing.mint_pairing_code(conn)
    registry = Registry(db_path)
    ws = _FakeWS()
    audit = AuditWriter(tmp_path / "audit")
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={},
        descriptors={}, audit=audit,
    )

    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=f"pair:{code}")
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert connection.device_id is not None
    welcome = Welcome.from_wire(Envelope.from_wire(json.loads(ws.sent[0])).payload)
    assert welcome.credential is not None

    # The registered device is discoverable and online now.
    assert registry.get(connection.device_id) is not None

    records = _read_audit_records(tmp_path / "audit")
    assert records[-1]["event"] == "paired"
    assert records[-1]["device_id"] == connection.device_id
    # No credential, plaintext or otherwise, ever reaches the audit line.
    assert "credential" not in json.dumps(records[-1]).lower()


async def test_hello_with_a_previously_consumed_pairing_code_is_auth_failed(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    code = pairing.mint_pairing_code(conn)
    assert pairing.consume_pairing_code(conn, code, "dev_already_paired") is True
    registry = Registry(db_path)
    ws = _FakeWS()
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={}, descriptors={}
    )

    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=f"pair:{code}")
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert ws.closed_with is not None
    assert connection.device_id is None


async def test_hello_with_a_returning_credential_resolves_the_same_device_id(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    credential = credentials.issue_credential(conn, "dev_1")
    registry = Registry(db_path)
    ws = _FakeWS()
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={}, descriptors={}
    )

    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=credential)
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert connection.device_id == "dev_1"

    welcome = Welcome.from_wire(Envelope.from_wire(json.loads(ws.sent[0])).payload)
    # No credential re-issued on a returning connection.
    assert welcome.credential is None


async def test_hello_with_a_revoked_credential_is_auth_failed(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'p', '', 0, 0, 'active')"
    )
    credential = credentials.issue_credential(conn, "dev_1")
    credentials.revoke_credential(conn, "dev_1")
    registry = Registry(db_path)
    ws = _FakeWS()
    connection = NodeConnection(
        ws, conn=conn, registry=registry, invocations=InvocationsMem(), connections={}, descriptors={}
    )

    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=credential)
    await connection._handle_frame(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))
    assert ws.closed_with is not None
    assert connection.device_id is None
