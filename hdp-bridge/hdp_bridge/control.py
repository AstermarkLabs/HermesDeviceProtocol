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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hdp_proto.capabilities import SchemaValidationError, validate_output
from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.errors import ErrorCode, err

from . import config
from . import revocation as _revocation
from .invocations import DeviceDisconnected

if TYPE_CHECKING:
    from hdp_proto.capabilities import CapabilityDescriptor

    from .connection import NodeConnection
    from .invocations import InvocationsMem
    from .registry import Registry

logger = logging.getLogger(__name__)

_MAX_FRAME_BYTES = 16 * 1024 * 1024
_REJECTED_VERBS = frozenset({"ctl_policy_set", "ctl_pair_mint"})


@dataclass(frozen=True)
class _InvokeReq:
    """Satisfies `connection.py`'s `_InvokeRequestLike` `Protocol` — `ctl_invoke`'s payload
    arrives as an untyped dict off the wire, and `NodeConnection.send_invoke` wants an object
    with these four attributes, not a dict."""

    capability: str
    version: int
    args: dict[str, Any]
    deadline_ms: int


def _invoke_failure(invocation_id: str, code: ErrorCode, detail: str) -> Envelope:
    """A failed `ctl_invoke_reply`, mirroring `embedded.py`'s `_failure` helper. `invocation_id`
    is `""` for the two failures that happen before an id is minted."""
    return Envelope.new(
        "ctl_invoke_reply",
        {"invocation_id": invocation_id, "ok": False, "error": err(code, detail)["error"]},
    )


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
        descriptors: dict[str, dict[str, CapabilityDescriptor]] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._registry = registry
        self._invocations = invocations
        self._connections = connections
        self._descriptors: dict[str, dict[str, CapabilityDescriptor]] = (
            descriptors if descriptors is not None else {}
        )
        # A raw `sqlite3.Connection`, distinct from `registry`'s own internal one (see
        # `daemon.py`'s NOTE on the two-connections deviation) — needed only by
        # `ctl_devices_revoke`, which operates below `Registry`'s device-record API via
        # `credentials.py`. `None` in tests that never exercise that verb.
        self._conn = conn
        self._raw_sock: socket.socket | None = None
        self._accept_task: asyncio.Task[None] | None = None
        self._active_writers: set[asyncio.StreamWriter] = set()

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

    async def _accept_loop(self) -> None:
        if self._raw_sock is None:
            raise RuntimeError("_accept_loop started before start() bound a listening socket")
        raw_sock = self._raw_sock
        loop = asyncio.get_running_loop()
        while True:
            conn, _addr = await loop.sock_accept(raw_sock)
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
        self._socket_path.unlink(missing_ok=True)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
                    await write_frame(writer, Envelope.new("error", error_payload).to_wire())
                    continue
                reply = await self._dispatch(envelope)
                await write_frame(writer, reply.to_wire())
        finally:
            self._active_writers.discard(writer)
            writer.close()

    async def _dispatch(self, envelope: Envelope) -> Envelope:
        if envelope.type in _REJECTED_VERBS:
            logger.warning("rejected control verb=%s (audited)", envelope.type)
            detail = f"{envelope.type} is not accepted on this connection"
            error_payload = err(ErrorCode.AUTH_FAILED, detail)["error"]
            return Envelope.new("error", error_payload)
        handler = {
            "ctl_list_devices": self._ctl_list_devices,
            "ctl_invoke": self._ctl_invoke,
            "ctl_cancel": self._ctl_cancel,
            "ctl_status": self._ctl_status,
            "ctl_devices_revoke": self._ctl_devices_revoke,
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
        """The plugin-reachable half of the ack-timeout/execution-deadline race — a faithful port
        of `EmbeddedTransport.invoke` (hermes_device_plugin/transport/embedded.py), adapted to
        operate on this server's own `_connections`/`_invocations`/`_descriptors` rather than an
        `EmbeddedTransport` instance's. See that file's docstring/comments for why each step is
        ordered the way it is (FR-30's removal-before-cancel rule, the ack/deadline split, the
        output-schema validation) — none of that reasoning is repeated here, only the code.
        """
        payload = envelope.payload
        device_id = payload.get("device_id")
        capability = payload.get("capability")
        version = payload.get("version")
        args = payload.get("args") or {}
        raw_deadline_ms = payload.get("deadline_ms")
        # `deadline_ms` arrives off the wire, unlike `embedded.py`'s dataclass-typed
        # `InvokeRequest` where it's always a real int. A missing/non-positive value is coerced
        # to `0` explicitly (not `or 0`'s incidental effect) so the execution-deadline
        # `wait_for` below fails fast with `invocation_timeout` instead of hanging or crashing on
        # a malformed frame — the ack race still runs and can still fail with `device_offline`
        # first, exactly as it would for a legitimately-short deadline.
        deadline_ms_is_valid = (
            isinstance(raw_deadline_ms, int)
            and not isinstance(raw_deadline_ms, bool)
            and raw_deadline_ms > 0
        )
        deadline_ms = raw_deadline_ms if deadline_ms_is_valid else 0

        if not device_id:
            return _invoke_failure(
                "", ErrorCode.NO_MATCHING_DEVICE, "invoke requires a resolved device_id"
            )

        connection = self._connections.get(device_id)
        if connection is None:
            return _invoke_failure("", ErrorCode.DEVICE_OFFLINE, "device is not connected")

        invocation_id, entry = self._invocations.mint_for(device_id, capability=capability or "")
        req = _InvokeReq(
            capability=capability or "", version=version or 0, args=args, deadline_ms=deadline_ms
        )
        await connection.send_invoke(invocation_id, req)

        # Ack timeout (5s), strictly less than the execution deadline (hdp-spec/HDP-0.md §7).
        try:
            await asyncio.wait_for(entry.ack_future, timeout=config.ACK_TIMEOUT_S)
        except TimeoutError:
            self._invocations.expire(invocation_id)  # remove first — FR-30's ordering rule
            await connection.send_cancel(invocation_id, "ack timeout")
            return _invoke_failure(
                invocation_id, ErrorCode.DEVICE_OFFLINE, "device did not ack within the timeout"
            )
        except DeviceDisconnected as exc:
            # `connection.py`'s disconnect handler (or `revocation.revoke_device`) already
            # removed the pending entry. `exc.reason` distinguishes an operator revocation
            # (`"revoked"`, FR-15) from an ordinary mid-call disconnect (`"device_offline"`).
            code = ErrorCode.REVOKED if exc.reason == "revoked" else ErrorCode.DEVICE_OFFLINE
            return _invoke_failure(invocation_id, code, "device disconnected before acking")

        deadline_s = deadline_ms / 1000
        try:
            result_payload = await asyncio.wait_for(entry.result_future, timeout=deadline_s)
        except TimeoutError:
            self._invocations.expire(invocation_id)  # remove first — FR-30's ordering rule
            await connection.send_cancel(invocation_id, "execution deadline exceeded")
            return _invoke_failure(
                invocation_id,
                ErrorCode.INVOCATION_TIMEOUT,
                "device did not return a result within its deadline",
            )
        except DeviceDisconnected as exc:
            code = ErrorCode.REVOKED if exc.reason == "revoked" else ErrorCode.DEVICE_OFFLINE
            return _invoke_failure(invocation_id, code, "device disconnected mid-call")

        return self._to_invoke_reply(invocation_id, device_id, capability, result_payload)

    def _to_invoke_reply(
        self, invocation_id: str, device_id: str, capability: str, result_payload: dict[str, Any]
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
        descriptor = self._descriptors.get(device_id, {}).get(capability)
        if descriptor is not None:
            try:
                validate_output(descriptor, data)
            except SchemaValidationError as exc:
                # `malformed_result` is what the model sees; `schema_drift` is the paired
                # log-only record (hdp-spec/errors.md's `schema_drift` entry) — mirrors
                # `embedded.py`'s `_to_invoke_result`.
                logger.warning(
                    "schema_drift capability=%s device_id=%s detail=%s", capability, device_id, exc
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
            connection = self._connections.get(entry.device_id)
            if connection is not None:
                await connection.send_cancel(invocation_id, reason)
            cancelled_result = {
                "ok": False,
                "error": err(ErrorCode.BRIDGE_UNAVAILABLE, reason)["error"],
            }
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

    async def _ctl_devices_revoke(self, envelope: Envelope) -> Envelope:
        """Operator-only verb (FR-15, §4.4) — the CLI's `hdp-bridge devices revoke` reaches this
        when a daemon is running, so the revoke frame and socket close happen against a live
        connection rather than the CLI's DB-only fallback (`cli.py`'s `_run_devices_revoke`)."""
        device_id = envelope.payload.get("device_id")
        if not device_id:
            error_payload = err(
                ErrorCode.NO_MATCHING_DEVICE, "revoke requires a device_id"
            )["error"]
            return Envelope.new("error", error_payload)
        if self._conn is None:  # pragma: no cover — always set in daemon.py's real wiring
            error_payload = err(
                ErrorCode.BRIDGE_UNAVAILABLE, "control server has no database connection"
            )["error"]
            return Envelope.new("error", error_payload)
        await _revocation.revoke_device(self._conn, device_id, connections=self._connections)
        return Envelope.new("ctl_devices_revoke_reply", {"ok": True, "device_id": device_id})
