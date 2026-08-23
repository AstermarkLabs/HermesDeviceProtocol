"""Per-connection lifecycle for one node's WebSocket.

One `NodeConnection` per accepted WebSocket. It owns the handshake (`hello` → `welcome`),
dispatches every subsequent frame by envelope type, tracks a per-connection malformed-frame
sliding window and envelope-id dedupe set (HDP-0.md §1, §5), and on disconnect fails every
in-flight invocation for its device immediately (HDP-0.md §7's "mid-call disconnect" rule) —
it must never wait for a deadline to notice the socket is gone.

`registry`, `invocations`, `connections`, and `descriptors` are shared across every connection on
one `EmbeddedTransport` (embedded.py constructs them once and passes the same objects to every
`NodeConnection`); this module never constructs its own copies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Protocol

from aiohttp import WSCloseCode, WSMsgType, web
from hdp_proto import ids
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope, EnvelopeError, UnsupportedVersionError
from hdp_proto.messages import (
    CancelMsg,
    CapabilitiesMsg,
    ErrorMsg,
    Hello,
    InvokeMsg,
    ResultMsg,
    Welcome,
)
from hdp_proto.version import HDP_VERSION

from . import credentials, pairing
from .types import CapabilityRecord, DeviceRecord

if TYPE_CHECKING:
    from .audit import AuditWriter
    from .invocations import InvocationsMem
    from .registry import Registry

logger = logging.getLogger(__name__)

_NODE_TO_BRIDGE_TYPES = frozenset(
    {"hello", "capabilities", "ack", "result", "progress", "heartbeat", "error"}
)
"""The subset of `hdp_proto.version.KNOWN_TYPES` a *node* may legally send. A frame with a
Bridge→Node-only type (`welcome`, `invoke`, `cancel`, `revoke`) arriving from a node is a known
message type used in the wrong direction — handled as a malformed frame (HDP-0.md §5), not a
version/type rejection at the envelope layer, since `Envelope.from_wire` has no notion of
direction."""

_MALFORMED_WINDOW_S = 60.0
_MALFORMED_LIMIT = 10
_SEEN_IDS_CAP = 256
_DEAD_PEER_TIMEOUT_S = 45.0


class _InvokeRequestLike(Protocol):
    capability: str
    version: int
    args: dict[str, Any]
    deadline_ms: int


class NodeConnection:
    """Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node connection."""

    def __init__(
        self,
        ws: web.WebSocketResponse,
        *,
        conn: sqlite3.Connection,
        registry: Registry,
        invocations: InvocationsMem,
        connections: dict[str, NodeConnection],
        descriptors: dict[str, dict[tuple[str, int], CapabilityDescriptor]],
        dead_peer_timeout_s: float = _DEAD_PEER_TIMEOUT_S,
        audit: AuditWriter | None = None,
    ) -> None:
        self._ws = ws
        self._conn = conn
        self._registry = registry
        self._invocations = invocations
        self._connections = connections
        self._descriptors = descriptors
        self._audit = audit
        self.device_id: str | None = None
        self._seen_ids: OrderedDict[str, None] = OrderedDict()
        self._malformed_times: list[float] = []
        self._dead_peer_timeout_s = dead_peer_timeout_s
        self._last_heartbeat = time.monotonic()
        self._disconnect_reason: str = "device_offline"
        """The reason `_on_disconnect` passes to `fail_all_for_device`. Ordinary socket drops
        never touch this (stays the default). `revocation.revoke_device` sets it to `"revoked"`
        *before* closing the socket — closing a real `aiohttp` WebSocket concurrently wakes this
        connection's own `run()` loop and races it against `revoke_device`'s own explicit
        fail-all-in-flight step; whichever of the two actually pops the pending entries must use
        `"revoked"`, not fall back to the ordinary-disconnect default, so this flag has to be set
        before the close happens, not after."""

    async def run(self) -> None:
        monitor_task = asyncio.create_task(self._dead_peer_monitor())
        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_frame(msg.data)
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            # `_on_disconnect()` runs first and un-shielded by any extra `await` ahead of it —
            # HDP-0.md §7's "mid-call disconnect fails in-flight invocations immediately" rule
            # means this cannot wait on anything else first. (An earlier draft cancelled+awaited
            # `monitor_task` *before* this call; that extra `await` gave aiohttp's own handler-
            # task teardown a window to deliver a `CancelledError` to `run()` itself right there,
            # which skipped `_on_disconnect()` entirely and let the mid-call ack-timeout fire
            # instead — reproduced against a real `aiohttp` `TestServer` in
            # `test_control.py::test_ctl_invoke_disconnect_mid_call_is_immediate`.)
            await self._on_disconnect()
            monitor_task.cancel()
            # Reap it so it can't outlive this `run()` call (a monitor task still `.cancel()`-
            # requested but never awaited can surface as "Task was destroyed but it is pending!"
            # once the event loop closes) — safe to do only now, after the invariant above holds.
            await asyncio.gather(monitor_task, return_exceptions=True)

    async def _dead_peer_monitor(self) -> None:
        """Started alongside `run()`'s own read loop and reaped in that same `finally`, on every
        exit path, so it can never outlive its `NodeConnection`. Polls for `_dead_peer_timeout_s`
        of silence since the last `heartbeat` frame; production's default 45s timeout is checked
        roughly once a second (`min(1.0, ...)` below clamps to 1.0 for any timeout >= 4s), while a
        test-only short override (see `test_presence.py`) gets a proportionally shorter poll
        interval so the check actually lands inside the test's wait window — a fixed 1s poll
        can't observe a 0.2s timeout within a 0.4s test budget.

        Calls `self._on_disconnect()` directly — *before* closing the socket, not after, so
        nothing (including this task's own subsequent `close()` await) can delay it — rather than
        relying solely on `run()`'s `async for` loop noticing the close and hitting its own
        `finally`. This module's docstring is explicit that the bridge "must never wait for a
        deadline to notice the socket is gone," and a real `aiohttp` `close()` performs a close
        handshake that can delay that loop's exit on an already-half-dead socket. `_on_disconnect`
        is idempotent
        (`mark_offline` re-write, `fail_all_for_device` on an already-empty pending set returns
        `[]`, `connections.pop(..., None)` is a no-op second time), so `run()`'s `finally` calling
        it again after this does no harm. Deliberately does NOT touch `_disconnect_reason` — a
        dead-peer timeout is an ordinary disconnect, not a revocation, so it stays at its
        `"device_offline"` default (see that attribute's docstring)."""
        poll_interval_s = max(0.01, min(1.0, self._dead_peer_timeout_s / 4))
        while True:
            await asyncio.sleep(poll_interval_s)
            if time.monotonic() - self._last_heartbeat > self._dead_peer_timeout_s:
                # Fail in-flight first, close second — same ordering argument as `run()`'s
                # `finally` (see its comment): `close()` yields control (a real `aiohttp` close
                # performs a handshake), which is exactly the kind of await that could let this
                # task's own cancellation land before `_on_disconnect()` runs, if something ever
                # raced to cancel this task at that exact point. Doing the fail-in-flight call
                # first makes the §7 immediacy guarantee unconditional rather than relying on
                # `run()`'s own `finally` as a fallback.
                await self._on_disconnect()
                await self._ws.close(code=WSCloseCode.GOING_AWAY, message=b"dead peer")
                return

    # -- outbound -----------------------------------------------------------------------------

    async def send_invoke(self, invocation_id: str, req: _InvokeRequestLike) -> None:
        msg = InvokeMsg(
            capability=req.capability,
            version=req.version,
            args=req.args,
            deadline_ms=req.deadline_ms,
        )
        envelope = Envelope.new("invoke", msg.to_wire(), corr=invocation_id)
        await self._ws.send_str(json.dumps(envelope.to_wire()))

    async def send_cancel(self, invocation_id: str, reason: str) -> None:
        """Best-effort — HDP-0.md §7: the caller has already removed the pending-table entry
        before calling this (FR-30's ordering rule lives in `_invocations.py`'s `expire()`), so a
        failed send here loses nothing."""
        msg = CancelMsg(reason=reason)
        envelope = Envelope.new("cancel", msg.to_wire(), corr=invocation_id)
        try:
            await self._ws.send_str(json.dumps(envelope.to_wire()))
        except ConnectionResetError:
            pass

    # -- inbound dispatch -----------------------------------------------------------------------

    async def _handle_frame(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as exc:
            await self._reject_malformed(f"invalid JSON: {exc}")
            return

        try:
            envelope = Envelope.from_wire(data)
        except UnsupportedVersionError:
            # HDP-0.md §3: close before any further processing, no `error` reply, no credential
            # read — a peer on a version we don't speak may not even parse our error envelope.
            await self._ws.close(
                code=WSCloseCode.POLICY_VIOLATION, message=b"unsupported hdp version"
            )
            return
        except EnvelopeError as exc:
            await self._reject_malformed(str(exc))
            return

        if envelope.id in self._seen_ids:
            # Envelope-id dedupe backstop (HDP-0.md §1, FR-34) — a duplicate frame (e.g. the
            # `duplicate-result` fault re-sending the exact same envelope) is silently ignored
            # here, on top of `InvocationsMem.resolve`'s own pop-once semantics.
            return
        self._remember_id(envelope.id)

        if self.device_id is None:
            if envelope.type != "hello":
                await self._ws.close(
                    code=WSCloseCode.PROTOCOL_ERROR, message=b"expected hello first"
                )
                return
            await self._handle_hello(envelope)
            return

        if envelope.type not in _NODE_TO_BRIDGE_TYPES:
            await self._reject_malformed(f"unexpected message direction: {envelope.type!r}")
            return

        handler = {
            "capabilities": self._handle_capabilities,
            "ack": self._handle_ack,
            "result": self._handle_result,
            "progress": self._handle_progress,
            "heartbeat": self._handle_heartbeat,
            "error": self._handle_error,
        }.get(envelope.type)
        if handler is None:  # pragma: no cover — "hello" is the only member excluded above
            await self._reject_malformed(f"unhandled type: {envelope.type!r}")
            return
        await handler(envelope)

    async def _handle_hello(self, envelope: Envelope) -> None:
        """M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing device's
        stored credential (a returning connection, resolved by hash — `hello` carries no
        device_id, only the credential, per `credentials.verify_credential_and_resolve_device`'s
        docstring) or a first-time pairing code, carried in the same `credential` field prefixed
        `pair:` (no wire-shape change — see hdp-spec/HDP-0.md's Amendments (v0.2)). There is no
        more anonymous/unpaired path: absent or invalid, in either form, closes the connection
        with `auth_failed`, full stop — this was only ever M1 scaffolding behavior."""
        try:
            hello = Hello.from_wire(envelope.payload)
        except ValueError as exc:
            await self._reject_malformed(f"malformed hello: {exc}")
            return

        if hello.credential and hello.credential.startswith("pair:"):
            await self._handle_pairing_hello(hello)
            return

        if not hello.credential:
            await self._ws.close(code=WSCloseCode.POLICY_VIOLATION, message=b"auth_failed")
            logger.warning("auth_failed device_name=%s reason=no_credential", hello.device_name)
            if self._audit is not None:
                self._audit.record("auth_failed", reason="no_credential")
            return

        device_id = credentials.verify_credential_and_resolve_device(self._conn, hello.credential)
        if device_id is None:
            await self._ws.close(code=WSCloseCode.POLICY_VIOLATION, message=b"auth_failed")
            logger.warning(
                "auth_failed device_name=%s reason=unknown_credential", hello.device_name
            )
            if self._audit is not None:
                self._audit.record("auth_failed", reason="unknown_credential")
            return

        self._register_device(device_id, hello)
        welcome = Welcome(hdp_version=int(HDP_VERSION), device_id=device_id)
        await self._send(Envelope.new("welcome", welcome.to_wire()))

    async def _handle_pairing_hello(self, hello: Hello) -> None:
        pair_code = hello.credential.removeprefix("pair:")  # type: ignore[union-attr]
        device_id = ids.new()
        if not pairing.consume_pairing_code(self._conn, pair_code, device_id):
            await self._ws.close(code=WSCloseCode.POLICY_VIOLATION, message=b"auth_failed")
            logger.warning("auth_failed reason=invalid_or_expired_pairing_code")
            if self._audit is not None:
                self._audit.record("auth_failed", reason="invalid_or_expired_pairing_code")
            return

        # `devices` must exist before `credentials` (FK constraint) — `_register_device` writes
        # the devices row (via `Registry`'s own connection to the same file; WAL mode makes the
        # commit visible to `self._conn` immediately) before `issue_credential` inserts against it.
        self._register_device(device_id, hello)
        new_credential = credentials.issue_credential(self._conn, device_id)
        welcome = Welcome(
            hdp_version=int(HDP_VERSION), device_id=device_id, credential=new_credential
        )
        await self._send(Envelope.new("welcome", welcome.to_wire()))
        if self._audit is not None:
            self._audit.record("paired", device_id=device_id)

    def _register_device(self, device_id: str, hello: Hello) -> None:
        capability_infos = [
            CapabilityRecord(
                name=c.name,
                version=c.version,
                input_schema=c.input_schema,
                output_schema=c.output_schema,
            )
            for c in hello.capabilities
        ]
        self._registry.register(
            DeviceRecord(
                device_id=device_id,
                friendly_name=hello.device_name,
                # Self-reported and advisory (HDP-0.md Amendments v0.3). Pre-v0.3 nodes omit it
                # and stay "unknown"; it is never consulted for an authorization decision.
                platform=hello.platform or "unknown",
                online=True,
                capabilities=capability_infos,
            )
        )
        self._descriptors[device_id] = {(c.name, c.version): c for c in hello.capabilities}
        self._connections[device_id] = self
        self.device_id = device_id

    async def _send(self, envelope: Envelope) -> None:
        await self._ws.send_str(json.dumps(envelope.to_wire()))

    async def _handle_capabilities(self, envelope: Envelope) -> None:
        try:
            msg = CapabilitiesMsg.from_wire(envelope.payload)
        except ValueError as exc:
            await self._reject_malformed(f"malformed capabilities: {exc}")
            return
        device_id = self.device_id
        if device_id is None:  # pragma: no cover — guaranteed by _handle_frame's dispatch gate
            raise RuntimeError("_handle_capabilities reached before device_id was assigned")
        if self._connections.get(device_id) is not self:
            logger.info("ignored stale capabilities device_id=%s", device_id)
            return
        existing = self._registry.get(device_id)
        friendly_name = existing.friendly_name if existing else device_id
        platform = existing.platform if existing else "unknown"
        capability_infos = [
            CapabilityRecord(
                name=c.name,
                version=c.version,
                input_schema=c.input_schema,
                output_schema=c.output_schema,
            )
            for c in msg.capabilities
        ]
        # Full-set replacement (FR-8), not a merge — matches `hello`'s initial registration.
        self._registry.register(
            DeviceRecord(
                device_id=device_id,
                friendly_name=friendly_name,
                platform=platform,
                online=True,
                capabilities=capability_infos,
            )
        )
        self._descriptors[device_id] = {(c.name, c.version): c for c in msg.capabilities}

    async def _handle_ack(self, envelope: Envelope) -> None:
        if envelope.corr is None:
            await self._reject_malformed("ack missing corr")
            return
        self._invocations.mark_acked(envelope.corr, connection=self)

    async def _handle_result(self, envelope: Envelope) -> None:
        if envelope.corr is None:
            await self._reject_malformed("result missing corr")
            return
        try:
            result_msg = ResultMsg.from_wire(envelope.payload)
        except ValueError as exc:
            await self._reject_malformed(f"malformed result: {exc}")
            return
        resolved = self._invocations.resolve(envelope.corr, result_msg.to_wire(), connection=self)
        if not resolved:
            # HDP-0.md §7: dropped silently on the model-facing side, logged here.
            logger.info("late_result invocation_id=%s device_id=%s", envelope.corr, self.device_id)

    async def _handle_progress(self, envelope: Envelope) -> None:
        pass  # declared per HDP-0.md §2; no M1 consumer

    async def _handle_heartbeat(self, envelope: Envelope) -> None:
        self._last_heartbeat = time.monotonic()
        if self.device_id is not None and self._connections.get(self.device_id) is self:
            with self._conn:
                self._conn.execute(
                    "UPDATE devices SET last_seen_at = ? WHERE device_id = ?",
                    (int(time.time() * 1000), self.device_id),
                )
        await self._send(Envelope.new("heartbeat", {}))

    async def _handle_error(self, envelope: Envelope) -> None:
        logger.info("node reported error device_id=%s payload=%s", self.device_id, envelope.payload)

    # -- malformed-frame bookkeeping ------------------------------------------------------------

    def _remember_id(self, envelope_id: str) -> None:
        self._seen_ids[envelope_id] = None
        if len(self._seen_ids) > _SEEN_IDS_CAP:
            self._seen_ids.popitem(last=False)

    def _record_malformed(self) -> bool:
        """Append now, drop anything outside the 60s window, and report whether the connection
        has now exceeded 10 malformed frames within that window (HDP-0.md §5)."""
        now = time.monotonic()
        self._malformed_times.append(now)
        cutoff = now - _MALFORMED_WINDOW_S
        self._malformed_times = [t for t in self._malformed_times if t >= cutoff]
        return len(self._malformed_times) > _MALFORMED_LIMIT

    async def _reject_malformed(self, message: str) -> None:
        error_msg = ErrorMsg(
            code="malformed_frame", message=message, hint="Send a well-formed HDP/0 frame."
        )
        envelope = Envelope.new("error", error_msg.to_wire())
        try:
            await self._ws.send_str(json.dumps(envelope.to_wire()))
        except ConnectionResetError:
            pass
        if self._record_malformed():
            await self._ws.close(
                code=WSCloseCode.PROTOCOL_ERROR, message=b"too many malformed frames"
            )

    # -- disconnect -----------------------------------------------------------------------------

    async def _on_disconnect(self) -> None:
        if self.device_id is None:
            return
        # A reconnect with the same credential replaces this mapping. The old connection may
        # unwind later, but it no longer owns presence and must not remove or fail the replacement.
        owns_presence = self._connections.get(self.device_id) is self
        if owns_presence:
            self._connections.pop(self.device_id)
        failed = self._invocations.fail_all_for_connection(self, reason=self._disconnect_reason)
        if failed:
            logger.info(
                "device_offline mid-call device_id=%s invocation_ids=%s", self.device_id, failed
            )
        # Memory-visible presence and pending state change before the SQLite timestamp write.
        if owns_presence:
            self._registry.mark_offline(self.device_id)
