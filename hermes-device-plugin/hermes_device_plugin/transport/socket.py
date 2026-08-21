"""M2 Unix-socket bridge transport — the client half of `hdp_bridge/control.py`'s framing.

`engine.py` never sees this module directly (it depends on `BridgeTransport`, transport/base.py);
this is what `runtime.py` swaps in once Task 7 flips the default (this task does not flip it — see
that task's brief). One persistent connection, opened eagerly by `start()` and reused across
every `_roundtrip` call, with jittered backoff on the lazy-reconnect path so a dead daemon doesn't
make every subsequent call pay OS-level connect-refused latency identically (design §5.3's
"reconnect" bullet, FR-14's node-side backoff shape reused here for the plugin side).

Requests are **multiplexed** over that one connection: `_roundtrip` registers a future keyed by
its envelope's `id`, writes the frame, and releases the lock; a single `_read_loop` task per
connection matches each reply's `corr` back to the right future. Until the M2 final review this
module instead held one lock across write *and* read, which made one in-flight device invocation
block every other call plugin-wide for its whole deadline — a functional regression from M1, and
the reason `cancel()` could never be delivered for the invocation it was cancelling. The server
half of that fix is `hdp_bridge/control.py`'s `_handle`/`_correlate` (finding I3).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time

from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.errors import ErrorCode, err

from .. import config
from .base import (
    BridgeStatus,
    CapabilityInfo,
    DeviceInfo,
    InvokeRequest,
    InvokeResult,
    PendingApproval,
)

logger = logging.getLogger(__name__)

_BACKOFF_INITIAL_S = 1.0
_BACKOFF_MAX_S = 30.0
_BACKOFF_JITTER_FRACTION = 0.25
_CONTROL_CANCEL_TIMEOUT_S = 0.5

_DEAD_CONNECTION_ERRORS = (
    ConnectionResetError,
    BrokenPipeError,
    asyncio.IncompleteReadError,
    OSError,
)
"""Raised by the write/read half of an already-open connection when the daemon disappears out
from under it. Caught in `_roundtrip` so a dropped connection surfaces as `bridge_unavailable`,
not an unhandled exception or a hang."""


def _bridge_unavailable(detail: str) -> Envelope:
    return Envelope.new("error", err(ErrorCode.BRIDGE_UNAVAILABLE, detail)["error"])


async def _read_frame(reader: asyncio.StreamReader) -> dict:
    header = await reader.readexactly(4)
    length = int.from_bytes(header, "big")
    body = await reader.readexactly(length)
    return json.loads(body)


async def _write_frame(writer: asyncio.StreamWriter, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    writer.write(len(body).to_bytes(4, "big") + body)
    await writer.drain()


class SocketTransport:
    """Implements `BridgeTransport` (verified structurally by the tests, not by explicit
    subclassing — `Protocol` is structural on purpose, see transport/base.py)."""

    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._backoff_s = _BACKOFF_INITIAL_S
        self._next_retry_at = 0.0
        # Replies are demultiplexed by envelope id, not by arrival order (finding I3). Each
        # connection gets its own `_pending` dict, owned jointly by `_roundtrip` (which registers
        # a future) and that connection's `_read_loop` task (which resolves it). Rebinding a
        # fresh dict per connection — rather than clearing one shared dict — is what makes a
        # dying reader task unable to fail a *newer* connection's in-flight requests as it
        # unwinds.
        self._pending: dict[str, asyncio.Future[Envelope]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Eagerly opens the connection once, matching `InprocTransport`/`EmbeddedTransport`'s
        `start()` semantics (`HDPRuntime` always calls `start()` before serving). Failure here is
        not fatal — it just means the first `invoke()`/etc. call retries the connect itself,
        same as every call after a mid-session disconnect."""
        async with self._lock:
            await self._connect_locked()

    async def close(self) -> None:
        async with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._reader_task is not None:
            # Its `finally` settles every future still in the `_pending` dict it owns, so a
            # caller parked in `_roundtrip` gets `bridge_unavailable` rather than hanging forever.
            self._reader_task.cancel()
            self._reader_task = None
        if self._writer is not None:
            self._writer.close()
        self._writer = None
        self._reader = None
        self._pending = {}

    async def _connect_locked(self) -> bool:
        """Attempt to (re)connect. Must be called with `self._lock` held. Returns `True` on
        success; on failure, schedules the next retry per the backoff schedule and returns
        `False` — never raises."""
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(
                str(config.control_socket_path())
            )
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            self._reader = None
            self._writer = None
            jitter = random.uniform(0, self._backoff_s * _BACKOFF_JITTER_FRACTION)  # noqa: S311
            # Not a security context — this is retry-storm jitter for a local reconnect loop, not
            # a cryptographic value.
            self._next_retry_at = time.monotonic() + self._backoff_s + jitter
            self._backoff_s = min(self._backoff_s * 2, _BACKOFF_MAX_S)
            return False
        self._backoff_s = _BACKOFF_INITIAL_S  # reset once a connection actually succeeds
        self._pending = {}
        self._reader_task = asyncio.ensure_future(self._read_loop(self._reader, self._pending))
        return True

    async def _read_loop(
        self, reader: asyncio.StreamReader, pending: dict[str, asyncio.Future[Envelope]]
    ) -> None:
        """Demultiplex every reply on one connection into the future that is waiting for it.

        One reader task per connection, for the connection's whole life — replacing the old
        write-then-read-under-one-lock round trip, which serialised *all* device invocations
        plugin-wide behind whichever one happened to be in flight (finding I3).
        """
        try:
            while True:
                raw = await _read_frame(reader)
                try:
                    reply = Envelope.from_wire(raw)
                except EnvelopeError as exc:
                    logger.warning("dropping malformed control frame from hdp-bridge: %s", exc)
                    continue
                future = pending.pop(reply.corr, None) if reply.corr else None
                if future is None:
                    # Either an uncorrelated reply (the daemon's malformed-envelope branch, which
                    # has no request id to echo) or one whose caller already gave up. Neither is
                    # actionable; dropping it must not take the connection down with it.
                    logger.debug("dropping uncorrelated control reply type=%s", reply.type)
                    continue
                if not future.done():
                    future.set_result(reply)
        except (asyncio.CancelledError, *_DEAD_CONNECTION_ERRORS):
            pass
        finally:
            # Whatever ended this loop — a lost connection, or `close()` cancelling it — every
            # caller still parked on a future for this connection must be released, or it waits
            # forever for a reply that can no longer arrive.
            lost = _bridge_unavailable("connection to hdp-bridge daemon was lost")
            for future in list(pending.values()):
                if not future.done():
                    future.set_result(lost)
            pending.clear()

    async def _roundtrip(self, envelope: Envelope) -> Envelope:
        """Send one request and await its reply, holding no lock while waiting.

        The lock covers connection setup and the write only. Waiting for the reply happens
        outside it, on a per-request future keyed by this envelope's id, so concurrent callers
        interleave instead of queueing behind each other's deadlines.
        """
        async with self._lock:
            if self._writer is None:
                if time.monotonic() < self._next_retry_at:
                    # Still within the backoff window from the last failed attempt — fail fast
                    # rather than paying OS-level connect-refused latency on every single call.
                    return _bridge_unavailable("cannot reach hdp-bridge daemon")
                if not await self._connect_locked():
                    return _bridge_unavailable("cannot reach hdp-bridge daemon")

            # Captured under the lock, and used for the rest of this call: a reconnect between
            # here and the reply must not make this request wait on a different connection's
            # `_pending` dict.
            pending = self._pending
            future: asyncio.Future[Envelope] = asyncio.get_running_loop().create_future()
            pending[envelope.id] = future
            try:
                await _write_frame(self._writer, envelope.to_wire())
            except _DEAD_CONNECTION_ERRORS:
                pending.pop(envelope.id, None)
                self._close_locked()
                return _bridge_unavailable("connection to hdp-bridge daemon was lost")

        try:
            return await future
        finally:
            pending.pop(envelope.id, None)

    async def invoke(self, req: InvokeRequest) -> InvokeResult:
        request_env = Envelope.new(
            "ctl_invoke",
            {
                "capability": req.capability,
                "acceptable_versions": list(req.acceptable_versions),
                "requested_device_id": req.requested_device_id,
                "args": req.args,
                "deadline_ms": req.deadline_ms,
                "meta": req.meta,
            },
        )
        try:
            reply = await self._roundtrip(request_env)
        except asyncio.CancelledError:
            # The daemon keys its off-loop invoke task by this original control request id.
            # Cancel it over the same multiplexed connection without closing or disturbing
            # unrelated calls that may still be using that socket.
            cancel = Envelope.new(
                "ctl_cancel",
                {
                    "control_request_id": request_env.id,
                    "reason": "plugin invocation cancelled",
                },
            )
            with contextlib.suppress(Exception):
                await asyncio.shield(
                    asyncio.wait_for(self._roundtrip(cancel), timeout=_CONTROL_CANCEL_TIMEOUT_S)
                )
            raise
        if reply.type == "error":
            return InvokeResult(invocation_id="", ok=False, error=reply.payload)
        payload = reply.payload
        if not payload.get("ok"):
            return InvokeResult(
                invocation_id=payload.get("invocation_id", ""), ok=False, error=payload.get("error")
            )
        return InvokeResult(
            invocation_id=payload.get("invocation_id", ""), ok=True, data=payload.get("data")
        )

    async def cancel(self, invocation_id: str, reason: str) -> None:
        request = Envelope.new("ctl_cancel", {"invocation_id": invocation_id, "reason": reason})
        await self._roundtrip(request)

    async def list_devices(self) -> list[DeviceInfo]:
        reply = await self._roundtrip(Envelope.new("ctl_list_devices", {}))
        if reply.type == "error":
            return []
        return [
            DeviceInfo(
                device_id=d["device_id"],
                friendly_name=d["friendly_name"],
                platform=d["platform"],
                online=d["online"],
                state=d.get("state", "active"),
                client_version=d.get("client_version", ""),
                first_paired_at=d.get("first_paired_at", 0),
                last_seen_at=d.get("last_seen_at", 0),
                capabilities=[
                    CapabilityInfo(name=c["name"], version=c["version"])
                    for c in d.get("capabilities", [])
                ],
            )
            for d in reply.payload.get("devices", [])
        ]

    async def status(self) -> BridgeStatus:
        reply = await self._roundtrip(Envelope.new("ctl_status", {}))
        if reply.type == "error":
            return BridgeStatus(healthy=False, detail=reply.payload.get("message", "unreachable"))
        return BridgeStatus(
            healthy=reply.payload["healthy"], detail=reply.payload.get("detail", "")
        )

    async def list_approvals(self) -> list[PendingApproval]:
        reply = await self._roundtrip(Envelope.new("ctl_list_approvals", {}))
        if reply.type == "error":
            return []
        return [
            PendingApproval(
                invocation_id=approval["invocation_id"],
                device_id=approval["device_id"],
                capability=approval["capability"],
                version=approval["version"],
                args_summary=approval["args_summary"],
                requesting_session=approval.get("requesting_session", ""),
                risk_class=approval.get("risk_class", ""),
                created_at=approval["created_at"],
                expires_at=approval["expires_at"],
            )
            for approval in reply.payload.get("approvals", [])
        ]

    async def resolve_approval(self, invocation_id: str, decision: str, scope: str) -> None:
        reply = await self._roundtrip(
            Envelope.new(
                "ctl_resolve_approval",
                {"invocation_id": invocation_id, "decision": decision, "scope": scope},
            )
        )
        if reply.type == "error":
            raise RuntimeError(reply.payload.get("message", "approval resolution failed"))

    async def ctl_audit_tail(self) -> list[dict]:
        """Operator-only verb, deliberately **not** on `BridgeTransport` — never reachable by the
        model (§4.2's three-closed-sets argument), only by `hermes hdp audit` / `/hdp audit`
        (Task 17). Lives here, not duplicated in `cli.py`, so those callers reuse this
        connection's framing/backoff/error-handling instead of re-opening a second raw socket."""
        reply = await self._roundtrip(Envelope.new("ctl_audit_tail", {}))
        if reply.type == "error":
            return []
        return reply.payload.get("lines", [])

    async def ctl_policy_show(self) -> dict:
        reply = await self._roundtrip(Envelope.new("ctl_policy_show", {}))
        return {} if reply.type == "error" else reply.payload

    async def ctl_policy_reload(self) -> dict:
        reply = await self._roundtrip(Envelope.new("ctl_policy_reload", {}))
        return {} if reply.type == "error" else reply.payload
