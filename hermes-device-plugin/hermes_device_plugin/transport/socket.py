"""M2 Unix-socket bridge transport — the client half of `hdp_bridge/control.py`'s framing.

`engine.py` never sees this module directly (it depends on `BridgeTransport`, transport/base.py);
this is what `runtime.py` swaps in once Task 7 flips the default (this task does not flip it — see
that task's brief). One persistent connection, opened eagerly by `start()` and reused across
every `_roundtrip` call, with jittered backoff on the lazy-reconnect path so a dead daemon doesn't
make every subsequent call pay OS-level connect-refused latency identically (design §5.3's
"reconnect" bullet, FR-14's node-side backoff shape reused here for the plugin side).
"""

from __future__ import annotations

import asyncio
import json
import random
import time

from hdp_proto.envelope import Envelope
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

_BACKOFF_INITIAL_S = 1.0
_BACKOFF_MAX_S = 30.0
_BACKOFF_JITTER_FRACTION = 0.25

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
        if self._writer is not None:
            self._writer.close()
        self._writer = None
        self._reader = None

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
        return True

    async def _roundtrip(self, envelope: Envelope) -> Envelope:
        async with self._lock:
            if self._writer is None:
                if time.monotonic() < self._next_retry_at:
                    # Still within the backoff window from the last failed attempt — fail fast
                    # rather than paying OS-level connect-refused latency on every single call.
                    return _bridge_unavailable("cannot reach hdp-bridge daemon")
                if not await self._connect_locked():
                    return _bridge_unavailable("cannot reach hdp-bridge daemon")

            try:
                await _write_frame(self._writer, envelope.to_wire())
                reply_raw = await _read_frame(self._reader)
            except _DEAD_CONNECTION_ERRORS:
                self._close_locked()
                return _bridge_unavailable("connection to hdp-bridge daemon was lost")
            return Envelope.from_wire(reply_raw)

    async def invoke(self, req: InvokeRequest) -> InvokeResult:
        request_env = Envelope.new(
            "ctl_invoke",
            {
                "device_id": req.device_id,
                "capability": req.capability,
                "version": req.version,
                "args": req.args,
                "deadline_ms": req.deadline_ms,
            },
        )
        reply = await self._roundtrip(request_env)
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
        raise NotImplementedError("approvals are not implemented until M3")

    async def resolve_approval(self, invocation_id: str, decision: str, scope: str) -> None:
        raise NotImplementedError("resolve_approval is not implemented until M3")
