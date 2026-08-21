from __future__ import annotations

import asyncio
import gc

import pytest
from hdp_bridge.approvals import ApprovalManager
from hdp_bridge.control import ControlServer
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.policy import PolicyTable
from hdp_bridge.registry import Registry
from hdp_bridge.store import db
from hdp_bridge.types import CapabilityRecord, DeviceRecord
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope


def _capability(
    version: int,
    *,
    output_schema: dict | None = None,
) -> CapabilityRecord:
    return CapabilityRecord(
        name="diagnostics.echo",
        version=version,
        input_schema={"type": "object"},
        output_schema=output_schema or {"type": "object"},
    )


def _device(device_id: str, *versions: int, friendly_name: str | None = None) -> DeviceRecord:
    return DeviceRecord(
        device_id=device_id,
        friendly_name=friendly_name or device_id,
        platform="linux",
        online=True,
        capabilities=[_capability(version) for version in versions],
    )


def _device_in_state(device_id: str, state: str) -> DeviceRecord:
    device = _device(device_id, 1)
    return DeviceRecord(
        device_id=device.device_id,
        friendly_name=device.friendly_name,
        platform=device.platform,
        online=device.online,
        state=state,
        capabilities=device.capabilities,
    )


def _request(
    *,
    requested_device_id: str | None = None,
    acceptable_versions: list[int] | None = None,
) -> Envelope:
    return Envelope.new(
        "ctl_invoke",
        {
            "capability": "diagnostics.echo",
            "acceptable_versions": acceptable_versions or [1],
            "requested_device_id": requested_device_id,
            "args": {"payload": {}},
            "deadline_ms": 1000,
            "meta": {},
        },
    )


class _ImmediateConnection:
    def __init__(self, invocations: InvocationsMem, *, before_result=None) -> None:
        self._invocations = invocations
        self._before_result = before_result
        self.sent = []

    async def send_invoke(self, invocation_id, request):
        self.sent.append(request)
        self._invocations.mark_acked(invocation_id)
        if self._before_result is not None:
            self._before_result()
        self._invocations.resolve(
            invocation_id,
            {"ok": True, "data": {"old": {}}},
        )

    async def send_cancel(self, invocation_id, reason):
        return None


class _StaticPolicy:
    def __init__(self, table: PolicyTable) -> None:
        self.table = table

    def reload(self):
        return False


class _MemoryAudit:
    def __init__(self) -> None:
        self.records = []

    def record(self, event, **fields):
        self.records.append({"event": event, **fields})


class _BlockingConnection:
    def __init__(
        self,
        invocations: InvocationsMem,
        *,
        fail_send: bool = False,
        ack: bool = True,
        fail_cancel: bool = False,
    ) -> None:
        self._invocations = invocations
        self._fail_send = fail_send
        self._ack = ack
        self._fail_cancel = fail_cancel
        self.sent = []
        self.cancelled = []

    async def send_invoke(self, invocation_id, request):
        self.sent.append(request)
        if self._fail_send:
            raise OSError("socket closed")
        if self._ack:
            self._invocations.mark_acked(invocation_id, connection=self)

    async def send_cancel(self, invocation_id, reason):
        self.cancelled.append((invocation_id, reason))
        if self._fail_cancel:
            raise OSError("cancel socket closed")


def _server(tmp_path, devices, *, connected=(), table=None, audit=None):
    db_path = tmp_path / "registry.db"
    registry = Registry(db_path)
    for device in devices:
        registry.register(device)
    invocations = InvocationsMem()
    connections = {device_id: _ImmediateConnection(invocations) for device_id in connected}
    conn = db.connect(db_path)
    policy = _StaticPolicy(table) if table is not None else None
    return (
        ControlServer(
            tmp_path / "bridge.sock",
            registry=registry,
            invocations=invocations,
            connections=connections,
            conn=conn,
            policy=policy,
            approvals=ApprovalManager(conn),
            audit=audit,
        ),
        registry,
        invocations,
        connections,
    )


async def test_implicit_resolution_with_no_online_candidate_fails_before_transmission(tmp_path):
    server, _registry, _invocations, _connections = _server(tmp_path, [_device("dev_offline", 1)])

    reply = await server._ctl_invoke(_request())

    assert reply.payload["error"]["code"] == "no_matching_device"


async def test_explicit_device_is_restrictive_and_offline_is_not_fallback(tmp_path):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device("dev_offline", 1), _device("dev_online", 1)],
        connected=("dev_online",),
    )

    reply = await server._ctl_invoke(_request(requested_device_id="dev_offline"))

    assert reply.payload["error"]["code"] == "device_offline"
    assert connections["dev_online"].sent == []


async def test_explicit_online_device_without_capability_is_capability_unsupported(tmp_path):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device("dev_target")],
        connected=("dev_target",),
    )

    reply = await server._ctl_invoke(_request(requested_device_id="dev_target"))

    assert reply.payload["error"]["code"] == "capability_unsupported"
    assert connections["dev_target"].sent == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capability", None),
        ("capability", ""),
        ("acceptable_versions", None),
        ("acceptable_versions", []),
        ("acceptable_versions", [True]),
        ("acceptable_versions", [0]),
        ("acceptable_versions", [-1]),
        ("acceptable_versions", [1, "2"]),
        ("acceptable_versions", [1, 1]),
        ("requested_device_id", 7),
        ("requested_device_id", ""),
        ("args", None),
        ("args", []),
        ("meta", None),
        ("meta", []),
        ("deadline_ms", None),
        ("deadline_ms", True),
        ("deadline_ms", 0),
        ("deadline_ms", -1),
    ],
)
async def test_malformed_invoke_is_rejected_before_transmission(tmp_path, field, value):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
    )
    request = _request(requested_device_id="dev_target")
    request.payload[field] = value

    reply = await server._ctl_invoke(request)

    assert reply.type == "error"
    assert reply.payload["code"] == "not_implemented"
    assert "malformed ctl_invoke" in reply.payload["message"]
    assert connections["dev_target"].sent == []


async def test_malformed_invoke_never_copies_unvalidated_args_into_audit(tmp_path):
    audit = _MemoryAudit()
    server, _registry, _invocations, _connections = _server(tmp_path, [], audit=audit)
    request = _request()
    request.payload["capability"] = None
    request.payload["args"] = {"unvalidated": "must-not-be-audited"}

    reply = await server._ctl_invoke(request)

    assert reply.type == "error"
    failed = next(record for record in audit.records if record["event"] == "invocation_failed")
    assert "args" not in failed
    assert "must-not-be-audited" not in str(audit.records)


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [("revoked", "device_offline"), ("pending", "device_offline")],
)
async def test_explicit_connected_device_must_be_active(tmp_path, state: str, expected_code: str):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device_in_state("dev_target", state)],
        connected=("dev_target",),
    )

    reply = await server._ctl_invoke(_request(requested_device_id="dev_target"))

    assert reply.payload["error"]["code"] == expected_code
    assert connections["dev_target"].sent == []


async def test_explicit_revoked_but_disconnected_device_is_offline(tmp_path):
    server, _registry, _invocations, _connections = _server(
        tmp_path,
        [_device_in_state("dev_target", "revoked")],
    )

    reply = await server._ctl_invoke(_request(requested_device_id="dev_target"))

    assert reply.payload["error"]["code"] == "device_offline"


async def test_implicit_resolution_excludes_connected_non_active_device(tmp_path):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device_in_state("dev_pending", "pending")],
        connected=("dev_pending",),
    )

    reply = await server._ctl_invoke(_request())

    assert reply.payload["error"]["code"] == "no_matching_device"
    assert connections["dev_pending"].sent == []


async def test_multiple_candidates_without_usable_default_are_structured_ambiguity(tmp_path):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [
            _device("dev_a", 1, friendly_name="Alpha"),
            _device("dev_b", 1, friendly_name="Beta"),
        ],
        connected=("dev_a", "dev_b"),
    )

    reply = await server._ctl_invoke(_request())

    assert reply.payload["error"]["code"] == "ambiguous_device"
    assert reply.payload["error"]["candidates"] == [
        {"device_id": "dev_a", "friendly_name": "Alpha"},
        {"device_id": "dev_b", "friendly_name": "Beta"},
    ]
    assert all(connection.sent == [] for connection in connections.values())


async def test_default_device_selects_candidate_and_highest_common_version(tmp_path):
    table = PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"diagnostics.echo": "always"},
            "devices": {},
            "default_device": {"diagnostics.echo": "dev_b"},
        },
        policy_seq=4,
    )
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device("dev_a", 1), _device("dev_b", 1, 2)],
        connected=("dev_a", "dev_b"),
        table=table,
    )

    reply = await server._ctl_invoke(_request(acceptable_versions=[1, 2]))

    assert reply.payload["ok"] is True
    assert connections["dev_a"].sent == []
    assert connections["dev_b"].sent[0].version == 2


async def test_version_mismatch_reports_both_lists_without_transmission(tmp_path):
    server, _registry, _invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 99)],
        connected=("dev_target",),
    )

    reply = await server._ctl_invoke(_request(acceptable_versions=[1, 2]))

    assert reply.payload["error"]["code"] == "version_incompatible"
    assert reply.payload["error"]["node_supports"] == [99]
    assert reply.payload["error"]["plugin_supports"] == [1, 2]
    assert connections["dev_target"].sent == []


async def test_result_validation_uses_descriptor_captured_before_readvertisement(tmp_path):
    old_schema = {
        "type": "object",
        "properties": {"old": {"type": "object"}},
        "required": ["old"],
    }
    new_schema = {
        "type": "object",
        "properties": {"new": {"type": "object"}},
        "required": ["new"],
    }
    db_path = tmp_path / "registry.db"
    registry = Registry(db_path)
    registry.register(
        DeviceRecord(
            device_id="dev_target",
            friendly_name="target",
            platform="linux",
            online=True,
            capabilities=[_capability(1, output_schema=old_schema)],
        )
    )
    invocations = InvocationsMem()
    descriptors = {
        "dev_target": {
            "diagnostics.echo": CapabilityDescriptor(
                "diagnostics.echo", 1, {"type": "object"}, old_schema
            )
        }
    }

    def readvertise():
        registry.register(
            DeviceRecord(
                device_id="dev_target",
                friendly_name="target",
                platform="linux",
                online=True,
                capabilities=[_capability(1, output_schema=new_schema)],
            )
        )
        descriptors["dev_target"]["diagnostics.echo"] = CapabilityDescriptor(
            "diagnostics.echo", 1, {"type": "object"}, new_schema
        )

    connection = _ImmediateConnection(invocations, before_result=readvertise)
    server = ControlServer(
        tmp_path / "bridge.sock",
        registry=registry,
        invocations=invocations,
        connections={"dev_target": connection},
        descriptors=descriptors,
    )

    reply = await server._ctl_invoke(_request(requested_device_id="dev_target"))

    assert reply.payload["ok"] is True


async def test_disconnect_interrupts_an_ask_before_node_transmission(tmp_path):
    table = PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"diagnostics.echo": "ask"},
            "devices": {},
        },
        policy_seq=1,
    )
    server, _registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
        table=table,
    )
    loop = asyncio.get_running_loop()
    reported = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: reported.append(context))
    try:
        task = asyncio.create_task(server._ctl_invoke(_request(requested_device_id="dev_target")))
        for _ in range(20):
            if len(invocations):
                break
            await asyncio.sleep(0)

        invocations.fail_all_for_device("dev_target")
        reply = await asyncio.wait_for(task, timeout=0.2)
        del task
        gc.collect()
        await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(previous_handler)

    assert reply.payload["error"]["code"] == "device_offline"
    assert connections["dev_target"].sent == []
    assert reported == []


async def test_cancelled_control_request_abandons_ask_and_invocation(tmp_path):
    table = PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"diagnostics.echo": "ask"},
            "devices": {},
        },
        policy_seq=1,
    )
    server, _registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
        table=table,
    )
    task = asyncio.create_task(server._ctl_invoke(_request(requested_device_id="dev_target")))
    for _ in range(20):
        if len(invocations):
            break
        await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(invocations) == 0
    assert server._approvals is not None
    assert server._approvals.list_pending() == []
    assert connections["dev_target"].sent == []


async def test_cancellation_after_dispatch_expires_and_sends_best_effort_cancel(tmp_path):
    audit = _MemoryAudit()
    server, registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
        audit=audit,
    )
    connection = _BlockingConnection(invocations)
    connections["dev_target"] = connection
    sentinel = "cancelled-full-args-audit-only"
    request = _request(requested_device_id="dev_target")
    request.payload["args"] = {"payload": {"sentinel": sentinel}}
    task = asyncio.create_task(server._ctl_invoke(request))
    for _ in range(20):
        if connection.sent:
            break
        await asyncio.sleep(0)
    assert connection.sent
    assert not task.done()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(invocations) == 0
    assert len(connection.cancelled) == 1
    assert connection.cancelled[0][1] == "control request cancelled"
    failed = next(record for record in audit.records if record["event"] == "invocation_failed")
    assert failed["code"] == "bridge_unavailable"
    assert failed["reason"] == "control_client_cancelled"
    assert failed["device_id"] == "dev_target"
    assert failed["args"] == {"payload": {"sentinel": sentinel}}
    assert sentinel not in str(registry.get("dev_target"))
    assert server._approvals is not None
    assert sentinel not in str(server._approvals.list_pending())
    checkpoint = db.connect(tmp_path / "registry.db")
    checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert sentinel.encode() not in (tmp_path / "registry.db").read_bytes()


async def test_send_failure_returns_device_offline_and_cleans_pending(tmp_path):
    audit = _MemoryAudit()
    server, registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
        audit=audit,
    )
    connection = _BlockingConnection(invocations, fail_send=True)
    connections["dev_target"] = connection
    sentinel = "failed-full-args-audit-only"
    request = _request(requested_device_id="dev_target")
    request.payload["args"] = {"payload": {"sentinel": sentinel}}

    reply = await server._ctl_invoke(request)

    assert reply.payload["error"]["code"] == "device_offline"
    assert len(invocations) == 0
    failed = next(record for record in audit.records if record["event"] == "invocation_failed")
    assert failed["args"] == {"payload": {"sentinel": sentinel}}
    assert sentinel not in str(registry.get("dev_target"))
    assert server._approvals is not None
    assert sentinel not in str(server._approvals.list_pending())
    checkpoint = db.connect(tmp_path / "registry.db")
    checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert sentinel.encode() not in (tmp_path / "registry.db").read_bytes()


async def test_ack_timeout_reply_survives_cancel_send_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("hdp_bridge.config.ACK_TIMEOUT_S", 0.01)
    server, _registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
    )
    connection = _BlockingConnection(invocations, ack=False, fail_cancel=True)
    connections["dev_target"] = connection

    reply = await server._ctl_invoke(_request(requested_device_id="dev_target"))

    assert reply.payload["error"]["code"] == "device_offline"
    assert len(invocations) == 0


async def test_cancel_targets_dispatch_generation_and_settles_even_when_send_fails(tmp_path):
    server, _registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
    )
    old = _BlockingConnection(invocations, fail_cancel=True)
    replacement = _BlockingConnection(invocations)
    connections["dev_target"] = replacement
    invocation_id, entry = invocations.mint_for("dev_target", connection=old)

    reply = await server._ctl_cancel(
        Envelope.new(
            "ctl_cancel",
            {"invocation_id": invocation_id, "reason": "caller stopped"},
        )
    )

    assert reply.type == "ctl_cancel_reply"
    assert reply.payload == {"ok": True}
    assert old.cancelled == [(invocation_id, "caller stopped")]
    assert replacement.cancelled == []
    assert not invocations.is_pending(invocation_id)
    assert entry.ack_future.done()
    result = await asyncio.wait_for(entry.result_future, timeout=0.1)
    assert result["ok"] is False
    assert result["error"]["code"] == "bridge_unavailable"


@pytest.mark.parametrize(
    ("devices", "connected", "invoke_envelope", "expected_code", "expected_device"),
    [
        ([], (), _request(), "no_matching_device", None),
        (
            [_device("dev_target", 1)],
            (),
            _request(requested_device_id="dev_target"),
            "device_offline",
            "dev_target",
        ),
        (
            [_device("dev_target")],
            ("dev_target",),
            _request(requested_device_id="dev_target"),
            "capability_unsupported",
            "dev_target",
        ),
        (
            [_device("dev_target", 99)],
            ("dev_target",),
            _request(requested_device_id="dev_target"),
            "version_incompatible",
            "dev_target",
        ),
    ],
)
async def test_resolution_failures_are_audited_with_available_context(
    tmp_path, devices, connected, invoke_envelope, expected_code, expected_device
):
    audit = _MemoryAudit()
    server, _registry, _invocations, _connections = _server(
        tmp_path, devices, connected=connected, audit=audit
    )

    await server._ctl_invoke(invoke_envelope)

    failed = [record for record in audit.records if record["event"] == "invocation_failed"]
    assert len(failed) == 1
    assert failed[0]["code"] == expected_code
    assert failed[0]["device_id"] == expected_device
    assert failed[0]["capability"] == "diagnostics.echo"
    assert failed[0]["args"] == invoke_envelope.payload["args"]


async def test_ambiguity_is_the_only_unaudited_resolution_failure(tmp_path):
    audit = _MemoryAudit()
    server, _registry, _invocations, _connections = _server(
        tmp_path,
        [_device("dev_a", 1), _device("dev_b", 1)],
        connected=("dev_a", "dev_b"),
        audit=audit,
    )

    await server._ctl_invoke(_request())

    assert [record for record in audit.records if record["event"] == "invocation_failed"] == []


async def test_sensitive_denial_audits_full_args_and_policy_snapshot_only_in_audit(tmp_path):
    table = PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"camera.capture": "deny"},
            "devices": {},
        },
        policy_seq=8,
    )
    audit = _MemoryAudit()
    db_path = tmp_path / "registry.db"
    registry = Registry(db_path)
    device = DeviceRecord(
        device_id="dev_camera",
        friendly_name="camera",
        platform="linux",
        online=True,
        capabilities=[
            CapabilityRecord(
                name="camera.capture",
                version=1,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ],
    )
    registry.register(device)
    invocations = InvocationsMem()
    connection = _ImmediateConnection(invocations)
    conn = db.connect(db_path)
    server = ControlServer(
        tmp_path / "bridge.sock",
        registry=registry,
        invocations=invocations,
        connections={"dev_camera": connection},
        conn=conn,
        policy=_StaticPolicy(table),
        approvals=ApprovalManager(conn),
        audit=audit,
    )
    secret_args = {"lens": "wide", "token": "audit-only"}
    request = Envelope.new(
        "ctl_invoke",
        {
            "capability": "camera.capture",
            "acceptable_versions": [1],
            "requested_device_id": "dev_camera",
            "args": secret_args,
            "deadline_ms": 1000,
            "meta": {},
        },
    )

    reply = await server._ctl_invoke(request)

    assert reply.payload["error"]["code"] == "policy_denied"
    sensitive = next(
        record for record in audit.records if record["event"] == "sensitive_invocation"
    )
    assert sensitive["args"] == secret_args
    assert sensitive["device_id"] == "dev_camera"
    assert sensitive["version"] == 1
    assert sensitive["policy_seq"] == 8
    assert sensitive["source"] == "global_default"
    assert "audit-only" not in str(registry.get("dev_camera"))
    assert "audit-only" not in str(ApprovalManager(conn).list_pending())
    failed = next(record for record in audit.records if record["event"] == "invocation_failed")
    assert failed["code"] == "policy_denied"
    assert failed["policy_seq"] == 8
    assert failed["source"] == "global_default"


async def test_ask_cycle_keeps_full_args_only_in_ordered_audit_records(tmp_path):
    table = PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"diagnostics.echo": "ask"},
            "devices": {},
        },
        policy_seq=9,
    )
    audit = _MemoryAudit()
    server, _registry, invocations, connections = _server(
        tmp_path,
        [_device("dev_target", 1)],
        connected=("dev_target",),
        table=table,
        audit=audit,
    )
    unique_tail = "fr37-tail-visible-only-in-audit"
    unique_value = f"ordinary-prefix-{'x' * 100}-{unique_tail}"
    secret_value = "fr37-secret-only-in-audit"  # noqa: S105 - non-credential test sentinel
    request = _request(requested_device_id="dev_target")
    request.payload["args"] = {"note": unique_value, "api_token": secret_value}
    task = asyncio.create_task(server._ctl_invoke(request))
    for _ in range(20):
        if len(invocations):
            break
        await asyncio.sleep(0)
    assert server._approvals is not None
    pending = server._approvals.list_pending()[0]
    assert unique_value not in pending.args_summary
    assert unique_tail not in pending.args_summary
    assert "ordinary-prefix" in pending.args_summary
    assert secret_value not in pending.args_summary

    server._approvals.resolve(
        pending.invocation_id,
        approved=True,
        scope="one_time",
        decided_by="test_operator",
    )
    reply = await task

    assert reply.payload["ok"] is True
    events = [record["event"] for record in audit.records]
    assert events.index("sensitive_invocation") < events.index("approval_requested")
    assert events.index("approval_requested") < events.index("approval_decided")
    sensitive = next(
        record for record in audit.records if record["event"] == "sensitive_invocation"
    )
    assert sensitive["args"] == {"note": unique_value, "api_token": secret_value}
    assert server._approvals.list_pending() == []

    registry_db = tmp_path / "registry.db"
    checkpoint = db.connect(registry_db)
    checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    persisted = registry_db.read_bytes()
    assert unique_value.encode() not in persisted
    assert unique_tail.encode() not in persisted
    assert secret_value.encode() not in persisted
    approval_rows = checkpoint.execute(
        "SELECT invocation_id, state, decided_by, scope FROM approvals"
    ).fetchall()
    assert [tuple(row) for row in approval_rows] == [
        (pending.invocation_id, "approved", "test_operator", "one_time")
    ]
    assert connections["dev_target"].sent
