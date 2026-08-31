"""Plugin↔bridge Unix-socket control plane (ADR-0004, HDP-0.md §2's "same envelope, same type
names" claim reused for a private type-name vocabulary — see this plan's Global Constraints for
the exact verb set). Length-prefixed JSON frames: 4-byte big-endian length, then that many bytes
of one JSON object.

`ctl_list_devices` was the only verb dispatched at Task 5. This task (Task 6) adds `ctl_invoke`,
`ctl_cancel`, and `ctl_status` — the three plugin-reachable verbs `SocketTransport` needs.
`ctl_invoke`'s body is a deliberate, faithful port of `hermes_device_plugin/transport/embedded.py`
`EmbeddedTransport.invoke`'s ack-timeout/execution-deadline race (that module is deleted in a
later task; this is where its logic lives on). `ctl_list_approvals`/`ctl_resolve_approval` are
**not** added here — M3 adds both the client call and the server handler together. An
unrecognized-but-known-wire-type verb (including those two, until M3) falls through `_dispatch`'s
`handler is None` branch and gets `not_implemented`, not a crash.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import socket
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from hdp_proto.capabilities import CapabilityDescriptor, SchemaValidationError, validate_output
from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.errors import ErrorCode, err

from . import config
from . import revocation as _revocation
from .approvals import ApprovalManager, ApprovalScope, ApprovalState, UnknownApprovalError
from .invocations import DeviceDisconnected, PendingInvocation
from .policy import Decision, Mode, PolicyEngine, PolicyTable

if TYPE_CHECKING:
    from .audit import AuditWriter
    from .connection import NodeConnection
    from .invocations import InvocationsMem
    from .registry import Registry

logger = logging.getLogger(__name__)

_MAX_FRAME_BYTES = 16 * 1024 * 1024
_REJECTED_VERBS = frozenset({"ctl_policy_set", "ctl_pair_mint"})
_SENSITIVE_CAPABILITIES = frozenset(
    {"camera.capture", "location.current", "screen.capture", "clipboard.read"}
)


@dataclass(frozen=True)
class _InvokeReq:
    """Satisfies `connection.py`'s `_InvokeRequestLike` `Protocol` — `ctl_invoke`'s payload
    arrives as an untyped dict off the wire, and `NodeConnection.send_invoke` wants an object
    with these four attributes, not a dict."""

    capability: str
    version: int
    args: dict[str, Any]
    deadline_ms: int


@dataclass(frozen=True)
class _ResolvedTarget:
    """One invocation's live selection and immutable dispatch descriptor."""

    device_id: str
    connection: NodeConnection
    version: int
    descriptor: CapabilityDescriptor


@dataclass(frozen=True)
class _ValidatedInvoke:
    """A control invocation after its untrusted payload has passed shape validation."""

    capability: str
    acceptable_versions: list[int]
    requested_device_id: str | None
    args: dict[str, Any]
    deadline_ms: int
    meta: dict[str, Any]


@dataclass(frozen=True)
class _ResolutionFailure:
    reply: Envelope
    device_id: str | None = None


def _invoke_failure(
    invocation_id: str,
    code: ErrorCode,
    detail: str,
    *,
    extras: dict[str, Any] | None = None,
) -> Envelope:
    """A failed `ctl_invoke_reply`, mirroring `embedded.py`'s `_failure` helper. `invocation_id`
    is `""` for the two failures that happen before an id is minted."""
    return Envelope.new(
        "ctl_invoke_reply",
        {
            "invocation_id": invocation_id,
            "ok": False,
            "error": err(code, detail, extras=extras)["error"],
        },
    )


def _malformed_invoke(detail: str) -> Envelope:
    """Use the control protocol's generic malformed-envelope reply for an invalid payload."""
    return Envelope.new(
        "error",
        err(ErrorCode.NOT_IMPLEMENTED, f"malformed ctl_invoke: {detail}")["error"],
    )


def _validate_invoke_payload(payload: dict[str, Any]) -> _ValidatedInvoke | Envelope:
    capability = payload.get("capability")
    if not isinstance(capability, str) or not capability:
        return _malformed_invoke("capability must be a non-empty string")

    acceptable_versions = payload.get("acceptable_versions")
    if not isinstance(acceptable_versions, list) or not acceptable_versions:
        return _malformed_invoke("acceptable_versions must be a non-empty list")
    if any(
        not isinstance(version, int) or isinstance(version, bool) or version <= 0
        for version in acceptable_versions
    ):
        return _malformed_invoke("acceptable_versions must contain positive integers")
    if len(set(acceptable_versions)) != len(acceptable_versions):
        return _malformed_invoke("acceptable_versions must not contain duplicates")

    requested_device_id = payload.get("requested_device_id")
    if requested_device_id is not None and (
        not isinstance(requested_device_id, str) or not requested_device_id
    ):
        return _malformed_invoke("requested_device_id must be null or a non-empty string")

    args = payload.get("args")
    if not isinstance(args, dict):
        return _malformed_invoke("args must be an object")
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return _malformed_invoke("meta must be an object")

    deadline_ms = payload.get("deadline_ms")
    if not isinstance(deadline_ms, int) or isinstance(deadline_ms, bool) or deadline_ms <= 0:
        return _malformed_invoke("deadline_ms must be a positive integer")

    return _ValidatedInvoke(
        capability=capability,
        acceptable_versions=acceptable_versions,
        requested_device_id=requested_device_id,
        args=args,
        deadline_ms=deadline_ms,
        meta=meta,
    )


def _approval_args_summary(args: object, *, byte_limit: int = 512) -> str:
    """Render approval-safe arguments without ever putting raw values into SQLite or prompts."""
    if not isinstance(args, dict):
        return "(0 fields, 0 bytes)"
    secret_markers = ("token", "secret", "password", "key", "credential", "authorization")
    parts: list[str] = []
    for key, value in args.items():
        name = str(key)
        rendered = (
            "<redacted>"
            if any(marker in name.lower() for marker in secret_markers)
            else repr(value)
        )
        parts.append(f"{name}={rendered[:80]}")
    summary = " ".join(parts) + f" ({len(args)} fields)"
    return summary.encode("utf-8")[:byte_limit].decode("utf-8", errors="ignore")


def _correlate(reply: Envelope, request: Envelope) -> Envelope:
    """Stamp `reply.corr` with the request envelope's `id`.

    Applied to *every* reply, not just `ctl_invoke_reply`, so the client's demultiplexer has one
    rule instead of two (finding I3). Replies used to arrive uncorrelated and be matched purely
    by arrival order, which is only sound while the server answers strictly in request order —
    exactly the property `_handle` gives up in order to let invocations overlap.
    """
    return replace(reply, corr=request.id)


def _log_task_exception(task: asyncio.Task) -> None:
    """`add_done_callback` hook for every fire-and-forget task this module spawns.

    Without it, an exception escaping such a task is stored on the task object and only ever
    surfaces as asyncio's "Task exception was never retrieved" message at garbage-collection
    time — arbitrarily later, with no context, and (because the daemon's stdout is what the
    conformance suite reads as `bridge_log`) as noise in an unrelated test's captured log.
    Retrieving it here turns a silent failure into a logged one (defense in depth, findings I3
    and I6)."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("control-plane task failed: %r", exc, exc_info=exc)


async def _cancel_and_drain(*futures: asyncio.Future[Any]) -> None:
    """Cancel unfinished lifecycle futures and consume every terminal exception."""
    for future in futures:
        if not future.done():
            future.cancel()
    await asyncio.gather(*futures, return_exceptions=True)


def _raise_if_cancelling() -> None:
    """Surface a cancel request that an await of an already-done future did not suspend for."""
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError


async def read_frame(reader: asyncio.StreamReader) -> dict:
    header = await reader.readexactly(4)
    length = int.from_bytes(header, "big")
    if length > _MAX_FRAME_BYTES:
        raise ValueError(f"control frame too large: {length} bytes")
    body = await reader.readexactly(length)
    return json.loads(body)


async def write_frame(writer: asyncio.StreamWriter, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    writer.write(len(body).to_bytes(4, "big") + body)
    await writer.drain()


class ControlServer:
    def __init__(
        self,
        socket_path: Path,
        *,
        registry: Registry,
        invocations: InvocationsMem,
        connections: dict[str, NodeConnection],
        descriptors: dict[str, dict[tuple[str, int], CapabilityDescriptor]] | None = None,
        conn: sqlite3.Connection | None = None,
        audit: AuditWriter | None = None,
        approvals: ApprovalManager | None = None,
        policy: PolicyEngine | None = None,
        usb_bootstrap: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._registry = registry
        self._invocations = invocations
        self._connections = connections
        self._descriptors: dict[str, dict[tuple[str, int], CapabilityDescriptor]] = (
            descriptors if descriptors is not None else {}
        )
        self._audit = audit
        self._approvals = approvals
        self._policy = policy
        self._usb_bootstrap = usb_bootstrap
        # A raw `sqlite3.Connection`, distinct from `registry`'s own internal one (see
        # `daemon.py`'s NOTE on the two-connections deviation) — needed only by
        # `ctl_devices_revoke`, which operates below `Registry`'s device-record API via
        # `credentials.py`. `None` in tests that never exercise that verb.
        self._conn = conn
        self._raw_sock: socket.socket | None = None
        self._accept_task: asyncio.Task[None] | None = None
        self._active_writers: set[asyncio.StreamWriter] = set()
        # Every in-flight `ctl_invoke`, which `_handle` runs off its read loop rather than
        # inline (finding I3). Server-level rather than per-connection so `close()` can account
        # for all of them; `_handle` also cancels its own connection's share on disconnect.
        self._invoke_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        # A hand-rolled accept loop over a raw socket, rather than `asyncio.start_unix_server`,
        # is deliberate: see `close()`'s docstring for the race this sidesteps. `listen()`'s
        # backlog of 100 matches `asyncio.start_unix_server`'s own default.
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._socket_path.unlink(missing_ok=True)
        self._raw_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._raw_sock.setblocking(False)
        self._raw_sock.bind(str(self._socket_path))
        self._raw_sock.listen(100)
        self._socket_path.chmod(0o600)
        self._accept_task = asyncio.ensure_future(self._accept_loop())
        # Defense in depth (finding I6): if anything ever does escape `_accept_loop`'s own
        # handling below, it must be visible rather than silently killing the daemon's ability to
        # accept control connections for the rest of the process lifetime.
        self._accept_task.add_done_callback(_log_task_exception)

    async def _accept_loop(self) -> None:
        if self._raw_sock is None:
            raise RuntimeError("_accept_loop started before start() bound a listening socket")
        raw_sock = self._raw_sock
        loop = asyncio.get_running_loop()
        while True:
            try:
                conn, _addr = await loop.sock_accept(raw_sock)
            except asyncio.CancelledError:
                raise
            except OSError as exc:
                # A transient accept failure — `EMFILE`/`ENFILE` (process or system fd table
                # full) being the realistic one — used to propagate straight out of this loop,
                # permanently deafening the daemon to new control connections with no visible
                # error at all, since nothing ever retrieved this task's exception (finding I6).
                # Back off briefly and keep serving: the condition that caused it is virtually
                # always temporary, and the alternative is a daemon that is alive but unreachable.
                logger.warning("control accept failed (%r); retrying", exc)
                await asyncio.sleep(0.05)
                continue
            try:
                conn.setblocking(False)
                reader = asyncio.StreamReader(loop=loop)
                protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
                transport, _ = await loop.connect_accepted_socket(lambda p=protocol: p, conn)
            except asyncio.CancelledError:
                # `close()` cancelled us while we were still wiring this connection up (we'd
                # already popped it off the kernel backlog via `sock_accept()`, so nobody else
                # will ever close it) — close the raw socket ourselves so it isn't leaked, then
                # let the cancellation propagate as usual.
                conn.close()
                raise
            except OSError as exc:
                # Same reasoning as the accept-side handler above, for the wiring-up half: this
                # one connection is lost (and its raw socket closed here so it isn't leaked), but
                # the loop survives to serve the next one.
                logger.warning("control connection setup failed (%r); dropping it", exc)
                conn.close()
                continue
            writer = asyncio.StreamWriter(transport, protocol, reader, loop)
            # Registering here, and *only* here — synchronous with respect to `_accept_loop`'s own
            # control flow, with no `await` between it and the `ensure_future` below — is what
            # makes `close()`'s accounting complete: by the time `close()` cancels this task and
            # awaits that cancellation, this connection is either (a) fully registered in
            # `_active_writers` already (this line already ran), or (b) still in-flight inside the
            # `try` block above, in which case the `except CancelledError` branch just above
            # closes it directly. There is no third state.
            self._active_writers.add(writer)
            asyncio.ensure_future(self._handle(reader, writer))

    async def close(self) -> None:
        """Two independent mechanisms — not a poll loop guessing how many event-loop ticks
        asyncio's own (opaque, undocumented-timing) accept pipeline needs — jointly account for
        every connection that can possibly exist at the moment `close()` is called, including one
        whose `connect()` completed at the OS level in the very same event-loop tick as this call
        (e.g. `SocketTransport.start()` connecting immediately before a caller tears the daemon
        down, with no intervening `await`):

        1. Cancelling `_accept_task` and awaiting it settles `_accept_loop` into exactly one of
           three states for whatever connection it was last handling: not yet popped off the
           kernel backlog at all (untouched by the cancellation — see the drain below), popped and
           mid-wiring (`_accept_loop`'s own `except CancelledError` branch closes the raw socket
           before re-raising), or already fully registered into `_active_writers` (handled by the
           force-close loop below, same as any other live connection).
        2. `sock_accept()`/`connect_accepted_socket()` only ever process one connection at a time,
           serially — a connection that arrived while `_accept_task` was busy wiring up an earlier
           one is still sitting, untouched, in the kernel's own accept backlog, invisible to
           anything in this process. Draining it directly off the raw listening socket here —
           `accept()` on a non-blocking socket returns immediately, either a queued connection or
           `BlockingIOError`, so this never waits for a connection that isn't already there — is
           the only way to account for it; nothing above ever gets a chance to.

        Together these leave no window: every connection that exists at the moment `close()` runs
        is either mid-flight inside `_accept_task` (mechanism 1), sitting in the kernel backlog
        (mechanism 2), or already in `_active_writers` (the force-close loop below) — not a fourth,
        unaccounted-for state.
        """
        if self._accept_task is not None:
            self._accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._accept_task
            self._accept_task = None
        if self._raw_sock is not None:
            while True:
                try:
                    conn, _addr = self._raw_sock.accept()
                except (BlockingIOError, OSError):
                    break
                conn.close()
            self._raw_sock.close()
            self._raw_sock = None
        # Force-close every live connection so a stopped daemon is actually stopped, not merely
        # deaf — nothing above touches a connection that already finished wiring up before
        # `close()` was ever called; that would otherwise leak the plugin's connection forever
        # (its `SocketTransport` would never observe the daemon going away).
        for writer in list(self._active_writers):
            writer.close()
        self._active_writers.clear()
        # In-flight `ctl_invoke` tasks now run off their connection's read loop (finding I3), so
        # closing the writers above no longer accounts for them — a task parked in `wait_for` on
        # an execution deadline would outlive this `close()` entirely. Cancel and settle them
        # here, so a stopped daemon leaves no orphaned work behind.
        invoke_tasks = list(self._invoke_tasks)
        for task in invoke_tasks:
            task.cancel()
        if invoke_tasks:
            await asyncio.gather(*invoke_tasks, return_exceptions=True)
        self._invoke_tasks.clear()
        self._socket_path.unlink(missing_ok=True)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Read loop for one control connection.

        `ctl_invoke` is dispatched *off* this loop, as its own task, rather than awaited inline
        (finding I3). Awaiting it here meant one in-flight device invocation blocked every other
        verb on this connection for its entire deadline — a functional regression from M1, where
        the bridge lived in-process and invocations genuinely overlapped. It also made
        `ctl_cancel` undeliverable by construction: the only connection that could carry a cancel
        was the one wedged inside the invoke being cancelled.

        Every other verb stays inline. They are all short, non-blocking, and serialising them
        preserves the obvious ordering guarantee for the operator verbs.
        """
        connection_tasks: set[asyncio.Task[None]] = set()
        request_tasks: dict[str, asyncio.Task[None]] = {}
        # One `write_frame` at a time per connection. `write_frame`'s single `writer.write(...)`
        # call keeps frames from splitting each other, but `writer.drain()` is not itself safe to
        # call concurrently on one `StreamWriter` — two callers racing it under backpressure can
        # trip asyncio's own `assert waiter is None` in `FlowControlMixin._drain_helper`, which
        # escapes `_invoke_and_reply`'s narrow except clause and orphans that reply (re-review
        # finding, round 2: I3's off-loop `ctl_invoke` dispatch made this reachable for the first
        # time — the read loop's own inline replies and an in-flight invoke's reply can now land
        # on the same writer at once).
        write_lock = asyncio.Lock()
        try:
            while True:
                try:
                    raw = await read_frame(reader)
                except asyncio.IncompleteReadError:
                    return
                try:
                    envelope = Envelope.from_wire(raw)
                except EnvelopeError as exc:
                    error_payload = err(ErrorCode.NOT_IMPLEMENTED, str(exc))["error"]
                    # No `corr`: there is no valid envelope here, so there is no id to echo. The
                    # client logs and drops replies it can't correlate.
                    async with write_lock:
                        await write_frame(writer, Envelope.new("error", error_payload).to_wire())
                    continue
                if envelope.type == "ctl_invoke":
                    task = asyncio.ensure_future(
                        self._invoke_and_reply(envelope, writer, write_lock)
                    )
                    connection_tasks.add(task)
                    request_tasks[envelope.id] = task
                    self._invoke_tasks.add(task)
                    task.add_done_callback(connection_tasks.discard)
                    task.add_done_callback(self._invoke_tasks.discard)
                    task.add_done_callback(
                        lambda _task, request_id=envelope.id: request_tasks.pop(request_id, None)
                    )
                    task.add_done_callback(_log_task_exception)
                    continue
                if envelope.type == "ctl_cancel" and isinstance(
                    envelope.payload.get("control_request_id"), str
                ):
                    request_id = envelope.payload["control_request_id"]
                    invoke_task = request_tasks.get(request_id)
                    if invoke_task is not None:
                        invoke_task.cancel()
                    reply = Envelope.new("ctl_cancel_reply", {"cancelled": invoke_task is not None})
                    async with write_lock:
                        await write_frame(writer, _correlate(reply, envelope).to_wire())
                    continue
                reply = await self._dispatch(envelope)
                async with write_lock:
                    await write_frame(writer, _correlate(reply, envelope).to_wire())
        finally:
            # This connection is gone; nothing is left to deliver its invoke replies to.
            for task in connection_tasks:
                task.cancel()
            self._active_writers.discard(writer)
            writer.close()

    async def _invoke_and_reply(
        self, envelope: Envelope, writer: asyncio.StreamWriter, write_lock: asyncio.Lock
    ) -> None:
        """Run one `ctl_invoke` to completion and write its reply.

        `write_lock` — shared with `_handle`'s read loop and every other in-flight
        `_invoke_and_reply` on this same connection — serialises the actual `write_frame` call.
        Frame boundaries alone were never the risk (one `writer.write(...)` per frame can't
        split); the risk was two callers awaiting `writer.drain()` on the same `StreamWriter` at
        once, which is not itself safe under backpressure. Holding this lock only around the
        write keeps concurrent invokes able to run concurrently — it is not the same lock that
        would reintroduce finding I3's serialization.
        """
        reply = await self._ctl_invoke(envelope)
        try:
            async with write_lock:
                await write_frame(writer, _correlate(reply, envelope).to_wire())
        except (ConnectionResetError, BrokenPipeError, OSError):
            # The caller disconnected while its invocation was in flight. Nothing to deliver to
            # and nothing to escalate — the invocation's own bookkeeping is already settled.
            logger.debug("dropped a ctl_invoke_reply for a closed control connection")

    async def _dispatch(self, envelope: Envelope) -> Envelope:
        if envelope.type in _REJECTED_VERBS:
            logger.warning("rejected control verb=%s (audited)", envelope.type)
            if self._audit is not None:
                self._audit.record("rejected_control_verb", verb=envelope.type)
            detail = f"{envelope.type} is not accepted on this connection"
            error_payload = err(ErrorCode.AUTH_FAILED, detail)["error"]
            return Envelope.new("error", error_payload)
        handler = {
            "ctl_list_devices": self._ctl_list_devices,
            "ctl_invoke": self._ctl_invoke,
            "ctl_cancel": self._ctl_cancel,
            "ctl_status": self._ctl_status,
            "ctl_devices_revoke": self._ctl_devices_revoke,
            "ctl_devices_list_detailed": self._ctl_devices_list_detailed,
            "ctl_audit_tail": self._ctl_audit_tail,
            "ctl_list_approvals": self._ctl_list_approvals,
            "ctl_resolve_approval": self._ctl_resolve_approval,
            "ctl_policy_show": self._ctl_policy_show,
            "ctl_policy_reload": self._ctl_policy_reload,
            "ctl_usb_bootstrap": self._ctl_usb_bootstrap,
        }.get(envelope.type)
        if handler is None:
            detail = f"unknown control verb {envelope.type!r}"
            error_payload = err(ErrorCode.NOT_IMPLEMENTED, detail)["error"]
            return Envelope.new("error", error_payload)
        return await handler(envelope)

    async def _ctl_list_devices(self, envelope: Envelope) -> Envelope:
        # `Registry.list_devices()` (M2 Task 10) never reports `online` — as of this task,
        # `online` is process-lifetime information the durable store deliberately doesn't
        # persist (see `hdp_bridge/registry.py`'s `Registry._to_record`). `self._connections`
        # (populated by `NodeConnection._handle_hello`/`_on_disconnect`) is the live source of
        # truth for which devices are actually connected right now, so overlay it here rather
        # than let every registered-but-disconnected device read back as permanently offline —
        # a full rework of this overlay (moving it onto `NodeConnection` itself) is Task 12's.
        devices = []
        for record in self._registry.list_devices():
            wire = record.to_wire()
            wire["online"] = record.device_id in self._connections
            devices.append(wire)
        return Envelope.new("ctl_list_devices_reply", {"devices": devices})

    async def _ctl_invoke(self, envelope: Envelope) -> Envelope:
        """Resolve live state, authorize one snapshot, dispatch, then validate."""
        validated = _validate_invoke_payload(envelope.payload)
        if isinstance(validated, Envelope):
            return self._audit_invoke_failure(
                validated,
                capability=envelope.payload.get("capability"),
                requested_device_id=envelope.payload.get("requested_device_id"),
            )
        capability = validated.capability
        acceptable_versions = validated.acceptable_versions
        requested_device_id = validated.requested_device_id
        args = validated.args
        meta = validated.meta
        deadline_ms = validated.deadline_ms

        # Capture one immutable policy snapshot before its first consumer (default-device
        # selection). The same object is used for authorization after selection and throughout
        # an ASK wait, even if a hot reload replaces PolicyEngine.table in the meantime.
        policy_table = None
        if self._policy is not None:
            self._policy.reload()
            policy_table = self._policy.table

        resolved = self._resolve_target(
            capability=capability,
            acceptable_versions=acceptable_versions,
            requested_device_id=requested_device_id,
            policy_table=policy_table,
        )
        if isinstance(resolved, _ResolutionFailure):
            return self._audit_invoke_failure(
                resolved.reply,
                capability=capability,
                requested_device_id=requested_device_id,
                selected_device_id=resolved.device_id,
                policy_table=policy_table,
                args=args,
            )
        device_id = resolved.device_id
        version = resolved.version
        connection = resolved.connection

        invocation_id, entry = self._invocations.mint_for(
            device_id,
            capability=capability,
            version=version,
            descriptor=resolved.descriptor,
            connection=connection,
        )
        decision = None
        if policy_table is not None:
            decision = policy_table.resolve(device_id, capability)
            if capability in _SENSITIVE_CAPABILITIES or decision.mode is Mode.ASK:
                self._record_sensitive_invocation(
                    invocation_id=invocation_id,
                    resolved=resolved,
                    decision=decision,
                    args=args,
                )
            requesting_session = meta.get("session_id")
            if not isinstance(requesting_session, str) or not requesting_session:
                requesting_session = None

            allowed = decision.mode in {Mode.SESSION, Mode.DEVICE, Mode.ALWAYS}
            if decision.mode is Mode.ASK and self._approvals is not None:
                allowed = self._approvals.has_session_grant(
                    requesting_session, device_id, capability
                ) or self._approvals.has_database_grant(device_id, capability)
                if not allowed:
                    pending = self._approvals.create(
                        invocation_id=invocation_id,
                        device_id=device_id,
                        capability=capability,
                        version=version,
                        args_summary=_approval_args_summary(args),
                        requesting_session=requesting_session,
                        risk_class="",
                    )
                    if self._audit is not None:
                        self._audit.record(
                            "approval_requested",
                            invocation_id=pending.invocation_id,
                            device_id=pending.device_id,
                            capability=pending.capability,
                            version=pending.version,
                            args_summary=pending.args_summary,
                            requesting_session=pending.requesting_session,
                            risk_class=pending.risk_class,
                            expires_at=pending.expires_at,
                        )
                    approval_task = asyncio.create_task(self._approvals.wait(invocation_id))
                    disconnect_future = entry.disconnect_future
                    if disconnect_future is None:  # pragma: no cover - minted entries always set it
                        raise RuntimeError("pending invocation has no disconnect signal")
                    try:
                        done, _pending = await asyncio.wait(
                            {approval_task, disconnect_future},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                    except asyncio.CancelledError:
                        self._approvals.abandon(invocation_id)
                        self._invocations.expire(invocation_id)
                        await _cancel_and_drain(
                            approval_task,
                            entry.ack_future,
                            entry.result_future,
                            disconnect_future,
                        )
                        self._record_cancelled_invocation(
                            invocation_id=invocation_id,
                            resolved=resolved,
                            decision=decision,
                            requested_device_id=requested_device_id,
                            args=args,
                        )
                        raise
                    if disconnect_future in done:
                        self._approvals.abandon(invocation_id)
                        reason = disconnect_future.result()
                        # `fail_all_for_device` also fails whichever lifecycle future is still
                        # outstanding. ASK is waiting on the separate disconnect signal, so it
                        # must drain those unused futures or asyncio reports their exceptions as
                        # unretrieved after this request returns.
                        await _cancel_and_drain(
                            approval_task,
                            entry.ack_future,
                            entry.result_future,
                        )
                        code = (
                            ErrorCode.REVOKED if reason == "revoked" else ErrorCode.DEVICE_OFFLINE
                        )
                        return self._audit_invoke_failure(
                            _invoke_failure(
                                invocation_id,
                                code,
                                "device disconnected while awaiting approval",
                            ),
                            capability=capability,
                            requested_device_id=requested_device_id,
                            resolved=resolved,
                            decision=decision,
                            policy_table=policy_table,
                            args=args,
                        )
                    resolution = approval_task.result()
                    if self._audit is not None:
                        self._audit.record(
                            "approval_decided",
                            invocation_id=invocation_id,
                            state=resolution.state.value,
                            scope=resolution.scope.value if resolution.scope is not None else None,
                            decided_by=resolution.decided_by,
                        )
                    if resolution.state is not ApprovalState.APPROVED:
                        self._invocations.expire(invocation_id)
                        code = (
                            ErrorCode.APPROVAL_TIMEOUT
                            if resolution.state is ApprovalState.EXPIRED
                            else ErrorCode.APPROVAL_DENIED
                        )
                        return self._audit_invoke_failure(
                            _invoke_failure(invocation_id, code, "approval was not granted"),
                            capability=capability,
                            requested_device_id=requested_device_id,
                            resolved=resolved,
                            decision=decision,
                            policy_table=policy_table,
                            args=args,
                        )
                    allowed = True
            if not allowed:
                self._invocations.expire(invocation_id)
                if self._audit is not None:
                    self._audit.record(
                        "policy_denied",
                        invocation_id=invocation_id,
                        device_id=device_id,
                        capability=capability,
                        source=decision.source,
                        policy_seq=decision.policy_seq,
                    )
                return self._audit_invoke_failure(
                    _invoke_failure(invocation_id, ErrorCode.POLICY_DENIED, "denied by policy"),
                    capability=capability,
                    requested_device_id=requested_device_id,
                    resolved=resolved,
                    decision=decision,
                    policy_table=policy_table,
                    args=args,
                )
        req = _InvokeReq(capability=capability, version=version, args=args, deadline_ms=deadline_ms)
        try:
            await connection.send_invoke(invocation_id, req)
            _raise_if_cancelling()
        except asyncio.CancelledError:
            await self._abort_dispatched(invocation_id, entry, connection)
            self._record_cancelled_invocation(
                invocation_id=invocation_id,
                resolved=resolved,
                decision=decision,
                requested_device_id=requested_device_id,
                args=args,
            )
            raise
        except Exception as exc:
            await self._abort_dispatched(invocation_id, entry, connection, send_cancel=False)
            return self._audit_invoke_failure(
                _invoke_failure(
                    invocation_id,
                    ErrorCode.DEVICE_OFFLINE,
                    f"failed to transmit invocation: {exc}",
                ),
                capability=capability,
                requested_device_id=requested_device_id,
                resolved=resolved,
                decision=decision,
                policy_table=policy_table,
                args=args,
            )

        # Ack timeout (5s), strictly less than the execution deadline (hdp-spec/HDP-0.md §7).
        try:
            # A cancel can arrive after `send_invoke` returns but before this task begins its ack
            # wait. Yield once so task cancellation is observed even when the ack future is
            # already done (awaiting an already-done future does not itself suspend).
            await asyncio.sleep(0)
            await asyncio.wait_for(entry.ack_future, timeout=config.ACK_TIMEOUT_S)
            _raise_if_cancelling()
        except asyncio.CancelledError:
            await self._abort_dispatched(invocation_id, entry, connection)
            self._record_cancelled_invocation(
                invocation_id=invocation_id,
                resolved=resolved,
                decision=decision,
                requested_device_id=requested_device_id,
                args=args,
            )
            raise
        except TimeoutError:
            self._invocations.expire(invocation_id)  # remove first — FR-30's ordering rule
            with contextlib.suppress(Exception):
                await connection.send_cancel(invocation_id, "ack timeout")
            return self._audit_invoke_failure(
                _invoke_failure(
                    invocation_id,
                    ErrorCode.DEVICE_OFFLINE,
                    "device did not ack within the timeout",
                ),
                capability=capability,
                requested_device_id=requested_device_id,
                resolved=resolved,
                decision=decision,
                policy_table=policy_table,
                args=args,
            )
        except DeviceDisconnected as exc:
            # `connection.py`'s disconnect handler (or `revocation.revoke_device`) already
            # removed the pending entry. `exc.reason` distinguishes an operator revocation
            # (`"revoked"`, FR-15) from an ordinary mid-call disconnect (`"device_offline"`).
            code = ErrorCode.REVOKED if exc.reason == "revoked" else ErrorCode.DEVICE_OFFLINE
            return self._audit_invoke_failure(
                _invoke_failure(invocation_id, code, "device disconnected before acking"),
                capability=capability,
                requested_device_id=requested_device_id,
                resolved=resolved,
                decision=decision,
                policy_table=policy_table,
                args=args,
            )

        deadline_s = deadline_ms / 1000
        try:
            result_payload = await asyncio.wait_for(entry.result_future, timeout=deadline_s)
            _raise_if_cancelling()
        except asyncio.CancelledError:
            await self._abort_dispatched(invocation_id, entry, connection)
            self._record_cancelled_invocation(
                invocation_id=invocation_id,
                resolved=resolved,
                decision=decision,
                requested_device_id=requested_device_id,
                args=args,
            )
            raise
        except TimeoutError:
            self._invocations.expire(invocation_id)  # remove first — FR-30's ordering rule
            with contextlib.suppress(Exception):
                await connection.send_cancel(invocation_id, "execution deadline exceeded")
            return self._audit_invoke_failure(
                _invoke_failure(
                    invocation_id,
                    ErrorCode.INVOCATION_TIMEOUT,
                    "device did not return a result within its deadline",
                ),
                capability=capability,
                requested_device_id=requested_device_id,
                resolved=resolved,
                decision=decision,
                policy_table=policy_table,
                args=args,
            )
        except DeviceDisconnected as exc:
            code = ErrorCode.REVOKED if exc.reason == "revoked" else ErrorCode.DEVICE_OFFLINE
            return self._audit_invoke_failure(
                _invoke_failure(invocation_id, code, "device disconnected mid-call"),
                capability=capability,
                requested_device_id=requested_device_id,
                resolved=resolved,
                decision=decision,
                policy_table=policy_table,
                args=args,
            )

        reply = self._to_invoke_reply(invocation_id, entry, result_payload)
        return self._audit_invoke_failure(
            reply,
            capability=capability,
            requested_device_id=requested_device_id,
            resolved=resolved,
            decision=decision,
            policy_table=policy_table,
            args=args,
        )

    def _audit_invoke_failure(
        self,
        reply: Envelope,
        *,
        capability: object,
        requested_device_id: object,
        resolved: _ResolvedTarget | None = None,
        selected_device_id: str | None = None,
        decision: Decision | None = None,
        policy_table: PolicyTable | None = None,
        args: dict[str, Any] | None = None,
    ) -> Envelope:
        error = reply.payload if reply.type == "error" else reply.payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if self._audit is None or not isinstance(code, str) or code == ErrorCode.AMBIGUOUS_DEVICE:
            return reply
        fields: dict[str, Any] = {
            "invocation_id": reply.payload.get("invocation_id", ""),
            "code": code,
            "capability": capability if isinstance(capability, str) else None,
            "requested_device_id": (
                requested_device_id if isinstance(requested_device_id, str) else None
            ),
            "device_id": (resolved.device_id if resolved is not None else selected_device_id),
            "version": resolved.version if resolved is not None else None,
            "policy_seq": policy_table.policy_seq if policy_table is not None else None,
            "source": decision.source if decision is not None else None,
        }
        if args is not None:
            fields["args"] = args
        self._audit.record("invocation_failed", **fields)
        return reply

    def _record_sensitive_invocation(
        self,
        *,
        invocation_id: str,
        resolved: _ResolvedTarget,
        decision: Decision,
        args: dict[str, Any],
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                "sensitive_invocation",
                invocation_id=invocation_id,
                device_id=resolved.device_id,
                capability=resolved.descriptor.name,
                version=resolved.version,
                policy_seq=decision.policy_seq,
                source=decision.source,
                args=args,
            )

    def _record_cancelled_invocation(
        self,
        *,
        invocation_id: str,
        resolved: _ResolvedTarget,
        decision: Decision | None,
        requested_device_id: str | None,
        args: dict[str, Any],
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                "invocation_failed",
                invocation_id=invocation_id,
                code=ErrorCode.BRIDGE_UNAVAILABLE.value,
                reason="control_client_cancelled",
                capability=resolved.descriptor.name,
                requested_device_id=requested_device_id,
                device_id=resolved.device_id,
                version=resolved.version,
                policy_seq=decision.policy_seq if decision is not None else None,
                source=decision.source if decision is not None else None,
                args=args,
            )

    async def _abort_dispatched(
        self,
        invocation_id: str,
        entry: PendingInvocation,
        connection: NodeConnection,
        *,
        send_cancel: bool = True,
    ) -> None:
        """Remove a cancelled/failed dispatch, then best-effort cancel and drain its futures."""
        self._invocations.expire(invocation_id)
        if send_cancel:
            with contextlib.suppress(Exception):
                await connection.send_cancel(invocation_id, "control request cancelled")
        futures = [entry.ack_future, entry.result_future]
        if entry.disconnect_future is not None:
            futures.append(entry.disconnect_future)
        await _cancel_and_drain(*futures)

    def _resolve_target(
        self,
        *,
        capability: str,
        acceptable_versions: list[int],
        requested_device_id: str | None,
        policy_table: PolicyTable | None,
    ) -> _ResolvedTarget | _ResolutionFailure:
        """Resolve one target synchronously so registry and connection state cannot interleave."""
        if requested_device_id:
            connection = self._connections.get(requested_device_id)
            record = self._registry.get(requested_device_id)
            if connection is None or record is None:
                return _ResolutionFailure(
                    _invoke_failure(
                        "",
                        ErrorCode.DEVICE_OFFLINE,
                        "the requested device is not active and online",
                    ),
                    requested_device_id,
                )
            if record.state != "active":
                return _ResolutionFailure(
                    _invoke_failure(
                        "",
                        ErrorCode.DEVICE_OFFLINE,
                        "the requested device is not active and online",
                    ),
                    requested_device_id,
                )
            capabilities = [cap for cap in record.capabilities if cap.name == capability]
            if not capabilities:
                return _ResolutionFailure(
                    _invoke_failure(
                        "",
                        ErrorCode.CAPABILITY_UNSUPPORTED,
                        "the requested device does not advertise this capability",
                    ),
                    requested_device_id,
                )
            selected_record = record
        else:
            candidates = sorted(
                (
                    record
                    for record in self._registry.list_devices()
                    if record.state == "active"
                    and record.device_id in self._connections
                    and any(cap.name == capability for cap in record.capabilities)
                ),
                key=lambda record: record.device_id,
            )
            if not candidates:
                return _ResolutionFailure(
                    _invoke_failure(
                        "",
                        ErrorCode.NO_MATCHING_DEVICE,
                        "no online device advertises this capability",
                    )
                )
            if len(candidates) > 1:
                configured_default = (
                    policy_table.default_device_for(capability)
                    if policy_table is not None
                    else None
                )
                selected_record = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.device_id == configured_default
                    ),
                    None,
                )
                if selected_record is None:
                    return _ResolutionFailure(
                        _invoke_failure(
                            "",
                            ErrorCode.AMBIGUOUS_DEVICE,
                            "multiple online devices advertise this capability",
                            extras={
                                "candidates": [
                                    {
                                        "device_id": candidate.device_id,
                                        "friendly_name": candidate.friendly_name,
                                    }
                                    for candidate in candidates
                                ]
                            },
                        )
                    )
            else:
                selected_record = candidates[0]
            connection = self._connections[selected_record.device_id]
            capabilities = [cap for cap in selected_record.capabilities if cap.name == capability]

        node_supports = sorted({cap.version for cap in capabilities})
        mutually_supported = set(node_supports).intersection(acceptable_versions)
        if not mutually_supported:
            return _ResolutionFailure(
                _invoke_failure(
                    "",
                    ErrorCode.VERSION_INCOMPATIBLE,
                    "device and plugin have no mutually supported capability version",
                    extras={
                        "node_supports": node_supports,
                        "plugin_supports": acceptable_versions,
                    },
                ),
                selected_record.device_id,
            )
        version = max(mutually_supported)
        selected_capability = next(cap for cap in capabilities if cap.version == version)
        descriptor = CapabilityDescriptor(
            name=selected_capability.name,
            version=selected_capability.version,
            input_schema=selected_capability.input_schema,
            output_schema=selected_capability.output_schema,
        )
        return _ResolvedTarget(selected_record.device_id, connection, version, descriptor)

    def _to_invoke_reply(
        self, invocation_id: str, entry: PendingInvocation, result_payload: dict[str, Any]
    ) -> Envelope:
        if not result_payload.get("ok"):
            error = result_payload.get("error")
            if not error:
                return _invoke_failure(
                    invocation_id,
                    ErrorCode.MALFORMED_RESULT,
                    "node returned failure with no error shape",
                )
            return Envelope.new(
                "ctl_invoke_reply", {"invocation_id": invocation_id, "ok": False, "error": error}
            )

        data = result_payload.get("data") or {}
        descriptor = entry.descriptor
        if descriptor is not None:
            try:
                validate_output(descriptor, data)
            except SchemaValidationError as exc:
                # `malformed_result` is what the model sees; `schema_drift` is the paired
                # log-only record (hdp-spec/errors.md's `schema_drift` entry) — mirrors
                # `embedded.py`'s `_to_invoke_result`.
                logger.warning(
                    "schema_drift capability=%s device_id=%s detail=%s",
                    entry.capability,
                    entry.device_id,
                    exc,
                )
                return _invoke_failure(invocation_id, ErrorCode.MALFORMED_RESULT, str(exc))
        return Envelope.new(
            "ctl_invoke_reply", {"invocation_id": invocation_id, "ok": True, "data": data}
        )

    async def _ctl_cancel(self, envelope: Envelope) -> Envelope:
        """Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call concurrently
        with an in-flight `_ctl_invoke` for the same id: it resolves the pending futures with a
        negative result rather than raising into them."""
        invocation_id = envelope.payload.get("invocation_id")
        reason = envelope.payload.get("reason", "")
        entry = self._invocations.expire(invocation_id) if invocation_id else None
        if entry is not None:
            cancelled_result = {
                "ok": False,
                "error": err(ErrorCode.BRIDGE_UNAVAILABLE, reason)["error"],
            }
            connection = cast("NodeConnection | None", entry.connection)
            try:
                if connection is not None:
                    await connection.send_cancel(invocation_id, reason)
            except Exception as exc:
                logger.info(
                    "best-effort cancel failed invocation_id=%s device_id=%s detail=%s",
                    invocation_id,
                    entry.device_id,
                    exc,
                )
            finally:
                if not entry.ack_future.done():
                    entry.ack_future.set_result(None)
                if not entry.result_future.done():
                    entry.result_future.set_result(cancelled_result)
        return Envelope.new("ctl_cancel_reply", {"ok": True})

    async def _ctl_status(self, envelope: Envelope) -> Envelope:
        return Envelope.new(
            "ctl_status_reply",
            {"healthy": True, "detail": f"{len(self._connections)} device(s) connected"},
        )

    async def _ctl_devices_list_detailed(self, envelope: Envelope) -> Envelope:
        """Operator-only verb (`hermes hdp devices` at Task 17 was ultimately built against the
        plugin-reachable `ctl_list_devices` instead, since `DeviceRecord.to_wire()` already
        carries `state`/`first_paired_at`/`last_seen_at` — see registry.py/types.py). This verb
        is kept as a genuine alias rather than deleted: it is pinned in `KNOWN_TYPES` as a
        distinct, operator-only wire type (§4.2's three-closed-sets argument), and a second body
        here would just duplicate `_ctl_list_devices` line for line for no behavioural gain."""
        reply = await self._ctl_list_devices(envelope)
        return Envelope.new("ctl_devices_list_detailed_reply", reply.payload)

    async def _ctl_audit_tail(self, envelope: Envelope) -> Envelope:
        """Operator-only verb backing `hermes hdp audit` / `/hdp audit` — read-only, but still
        goes through the control socket rather than a direct file read (brief Step 5) so it works
        identically regardless of whether the calling process can see the daemon's filesystem
        under a different profile's permissions."""
        lines = self._audit.read_today() if self._audit is not None else []
        return Envelope.new("ctl_audit_tail_reply", {"lines": lines})

    async def _ctl_list_approvals(self, envelope: Envelope) -> Envelope:
        """Return daemon-memory approvals; none are durable while pending."""
        approvals = self._approvals.list_pending() if self._approvals is not None else []
        return Envelope.new(
            "ctl_list_approvals_reply",
            {
                "approvals": [
                    {
                        "invocation_id": approval.invocation_id,
                        "device_id": approval.device_id,
                        "capability": approval.capability,
                        "version": approval.version,
                        "args_summary": approval.args_summary,
                        "requesting_session": approval.requesting_session,
                        "risk_class": approval.risk_class,
                        "created_at": approval.created_at,
                        "expires_at": approval.expires_at,
                    }
                    for approval in approvals
                ]
            },
        )

    async def _ctl_resolve_approval(self, envelope: Envelope) -> Envelope:
        if self._approvals is None:
            return Envelope.new(
                "error", err(ErrorCode.NOT_IMPLEMENTED, "approvals unavailable")["error"]
            )
        payload = envelope.payload
        invocation_id = payload.get("invocation_id")
        decision = payload.get("decision")
        scope = payload.get("scope", "one_time")
        if not isinstance(invocation_id, str) or decision not in {"approve", "deny"}:
            return Envelope.new(
                "error", err(ErrorCode.APPROVAL_DENIED, "invalid approval decision")["error"]
            )
        try:
            resolution = self._approvals.resolve(
                invocation_id,
                approved=decision == "approve",
                scope=ApprovalScope(scope),
                decided_by="control_plane",
            )
        except (UnknownApprovalError, ValueError):
            return Envelope.new(
                "error", err(ErrorCode.APPROVAL_DENIED, "approval is no longer pending")["error"]
            )
        return Envelope.new(
            "ctl_resolve_approval_reply",
            {
                "ok": True,
                "state": resolution.state.value,
                "scope": resolution.scope.value if resolution.scope is not None else None,
            },
        )

    async def _ctl_policy_show(self, envelope: Envelope) -> Envelope:
        if self._policy is None:
            return Envelope.new(
                "error", err(ErrorCode.NOT_IMPLEMENTED, "policy unavailable")["error"]
            )
        table = self._policy.table
        return Envelope.new(
            "ctl_policy_show_reply",
            {
                "policy_seq": table.policy_seq,
                "defaults": {capability: mode.value for capability, mode in table.defaults},
                "devices": {
                    device_id: {capability: mode.value for capability, mode in modes}
                    for device_id, modes in table.devices
                },
                "default_device": dict(table.default_devices),
            },
        )

    async def _ctl_policy_reload(self, envelope: Envelope) -> Envelope:
        if self._policy is None:
            return Envelope.new(
                "error", err(ErrorCode.NOT_IMPLEMENTED, "policy unavailable")["error"]
            )
        reloaded = self._policy.reload(force=True)
        return Envelope.new(
            "ctl_policy_reload_reply",
            {"ok": reloaded, "policy_seq": self._policy.table.policy_seq},
        )

    async def _ctl_usb_bootstrap(self, envelope: Envelope) -> Envelope:
        if self._usb_bootstrap is None:
            return Envelope.new(
                "error", err(ErrorCode.NOT_IMPLEMENTED, "USB bootstrap is unavailable")["error"]
            )
        serial = envelope.payload.get("serial", "")
        if not isinstance(serial, str):
            return Envelope.new(
                "error",
                err(ErrorCode.AUTH_FAILED, "USB serial must be a string")["error"],
            )
        try:
            enrollment_id = await self._usb_bootstrap(serial)
        except Exception as exc:  # noqa: BLE001 -- USB/Polkit failures are local operator feedback
            logger.warning("USB bootstrap failed: %s", exc)
            return Envelope.new(
                "error", err(ErrorCode.AUTH_FAILED, f"USB bootstrap refused: {exc}")["error"]
            )
        return Envelope.new("ctl_usb_bootstrap_reply", {"ok": True, "enrollment_id": enrollment_id})

    async def _ctl_devices_revoke(self, envelope: Envelope) -> Envelope:
        """Operator-only verb (FR-15, §4.4) — the CLI's `hdp devices revoke` reaches this
        when a daemon is running, so the revoke frame and socket close happen against a live
        connection rather than the CLI's DB-only fallback (`cli.py`'s `_run_devices_revoke`)."""
        device_id = envelope.payload.get("device_id")
        if not device_id:
            error_payload = err(ErrorCode.NO_MATCHING_DEVICE, "revoke requires a device_id")[
                "error"
            ]
            return Envelope.new("error", error_payload)
        if self._conn is None:  # pragma: no cover — always set in daemon.py's real wiring
            error_payload = err(
                ErrorCode.BRIDGE_UNAVAILABLE, "control server has no database connection"
            )["error"]
            return Envelope.new("error", error_payload)
        affected = await _revocation.revoke_device(
            self._conn, device_id, connections=self._connections, audit=self._audit
        )
        if affected == 0:
            # Nothing was actually revoked — unknown device_id, or already revoked. An `error`
            # envelope rather than a success reply so the operator CLI's reply-type check
            # (`operations.revoke`) surfaces it through the same path as any other failure
            # instead of printing "revoked <id>" for a no-op (final-review finding I4).
            error_payload = err(
                ErrorCode.NO_MATCHING_DEVICE, f"no live credential for device {device_id}"
            )["error"]
            return Envelope.new("error", error_payload)
        return Envelope.new("ctl_devices_revoke_reply", {"ok": True, "device_id": device_id})
