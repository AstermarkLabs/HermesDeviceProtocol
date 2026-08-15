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
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hdp_proto.capabilities import SchemaValidationError, validate_output
from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.errors import ErrorCode, err

from . import config
from .invocations import DeviceDisconnected

if TYPE_CHECKING:
    from hdp_proto.capabilities import CapabilityDescriptor

    from .connection import NodeConnection
    from .invocations import InvocationsMem
    from .registry import RegistryMem

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
        registry: RegistryMem,
        invocations: InvocationsMem,
        connections: dict[str, NodeConnection],
        descriptors: dict[str, dict[str, CapabilityDescriptor]] | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._registry = registry
        self._invocations = invocations
        self._connections = connections
        self._descriptors: dict[str, dict[str, CapabilityDescriptor]] = (
            descriptors if descriptors is not None else {}
        )
        self._server: asyncio.Server | None = None
        self._active_writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._socket_path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(self._handle, path=str(self._socket_path))
        self._socket_path.chmod(0o600)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        # `Server.close()` only stops accepting new connections — it leaves every already-open
        # control-socket connection running, which would otherwise leak the plugin's connection
        # forever (its `SocketTransport` would never observe the daemon going away). Force-close
        # every live connection so a stopped daemon is actually stopped, not merely deaf.
        for writer in list(self._active_writers):
            writer.close()
        self._active_writers.clear()
        self._socket_path.unlink(missing_ok=True)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._active_writers.add(writer)
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
        }.get(envelope.type)
        if handler is None:
            detail = f"unknown control verb {envelope.type!r}"
            error_payload = err(ErrorCode.NOT_IMPLEMENTED, detail)["error"]
            return Envelope.new("error", error_payload)
        return await handler(envelope)

    async def _ctl_list_devices(self, envelope: Envelope) -> Envelope:
        devices = [d.to_wire() for d in self._registry.list_devices()]
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
        except DeviceDisconnected:
            # `connection.py`'s disconnect handler already removed the pending entry.
            return _invoke_failure(
                invocation_id, ErrorCode.DEVICE_OFFLINE, "device disconnected before acking"
            )

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
        except DeviceDisconnected:
            return _invoke_failure(
                invocation_id, ErrorCode.DEVICE_OFFLINE, "device disconnected mid-call"
            )

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
