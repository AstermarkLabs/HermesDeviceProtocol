"""`EmbeddedTransport` — the concrete `BridgeTransport` `engine.py` talks to in production at M1.

Composes `_server.py` (the aiohttp `Application`), `_connection.py` (per-connection lifecycle),
`_invocations.py`, and `_registry_mem.py` into the real socket M1 exists to retire the risk of
(m1-plan.md's header risk statement). Has no `hdp_bridge` counterpart — at M2 this class is
replaced outright by `socket.py`, a Unix-socket client to the extracted daemon; unlike
`_server.py`/`_connection.py`, there is nothing here for that extraction to `git mv`.

`transport/inproc.py` stays the fast, dependency-free test stub it always was — this module is
the one that imports `aiohttp`, not that one.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from hdp_proto.capabilities import CapabilityDescriptor, SchemaValidationError, validate_output
from hdp_proto.errors import ErrorCode, err

from .. import config
from ._connection import NodeConnection
from ._invocations import DeviceDisconnected, InvocationsMem
from ._registry_mem import RegistryMem
from ._server import EmbeddedServer
from .base import BridgeStatus, DeviceInfo, InvokeRequest, InvokeResult, PendingApproval

logger = logging.getLogger(__name__)


def _failure(invocation_id: str, code: ErrorCode, detail: str) -> InvokeResult:
    """A failed `InvokeResult` carrying the model-facing error shape `errors.err` produces.
    `invocation_id` is `""` for the two failures that happen before an id is minted."""
    return InvokeResult(invocation_id=invocation_id, ok=False, error=err(code, detail)["error"])


class EmbeddedTransport:
    """Implements `BridgeTransport` (verified structurally by the tests, same as `InprocTransport`
    — `Protocol` is structural on purpose, see transport/base.py)."""

    def __init__(self) -> None:
        self._registry = RegistryMem()
        self._invocations = InvocationsMem()
        self._connections: dict[str, NodeConnection] = {}
        self._descriptors: dict[str, dict[str, CapabilityDescriptor]] = {}
        self._server = EmbeddedServer(self._make_connection)

    def _make_connection(self, ws: object) -> NodeConnection:
        return NodeConnection(
            ws,  # type: ignore[arg-type]  # aiohttp.web.WebSocketResponse; kept untyped here to
            # avoid this constructor-time helper importing aiohttp's request/response types just
            # for an annotation `_server.py` already types correctly at its own call site.
            registry=self._registry,
            invocations=self._invocations,
            connections=self._connections,
            descriptors=self._descriptors,
        )

    async def start(self) -> None:
        await self._server.start()

    async def close(self) -> None:
        await self._server.close()
        failed = self._invocations.fail_all()
        if failed:  # pragma: no cover — defensive; the per-connection disconnect path normally
            # empties the table before shutdown ever reaches here.
            logger.info("bridge_unavailable at shutdown, invocation_ids=%s", failed)

    async def invoke(self, req: InvokeRequest) -> InvokeResult:
        if req.device_id is None:
            return _failure(
                "", ErrorCode.NO_MATCHING_DEVICE, "invoke requires a resolved device_id"
            )

        connection = self._connections.get(req.device_id)
        if connection is None:
            return _failure("", ErrorCode.DEVICE_OFFLINE, "device is not connected")

        invocation_id, entry = self._invocations.mint_for(req.device_id, capability=req.capability)
        await connection.send_invoke(invocation_id, req)

        # Ack timeout (5s), strictly less than the execution deadline (hdp-spec/HDP-0.md §7).
        try:
            await asyncio.wait_for(entry.ack_future, timeout=config.ACK_TIMEOUT_S)
        except TimeoutError:
            self._invocations.expire(invocation_id)  # remove first — FR-30's ordering rule
            await connection.send_cancel(invocation_id, "ack timeout")
            return _failure(
                invocation_id, ErrorCode.DEVICE_OFFLINE, "device did not ack within the timeout"
            )
        except DeviceDisconnected:
            # `_connection.py`'s disconnect handler already removed the pending entry.
            return _failure(
                invocation_id, ErrorCode.DEVICE_OFFLINE, "device disconnected before acking"
            )

        deadline_s = req.deadline_ms / 1000
        try:
            result_payload = await asyncio.wait_for(entry.result_future, timeout=deadline_s)
        except TimeoutError:
            self._invocations.expire(invocation_id)  # remove first — FR-30's ordering rule
            await connection.send_cancel(invocation_id, "execution deadline exceeded")
            return _failure(
                invocation_id,
                ErrorCode.INVOCATION_TIMEOUT,
                "device did not return a result within its deadline",
            )
        except DeviceDisconnected:
            return _failure(invocation_id, ErrorCode.DEVICE_OFFLINE, "device disconnected mid-call")

        return self._to_invoke_result(invocation_id, req, result_payload)

    def _to_invoke_result(
        self, invocation_id: str, req: InvokeRequest, result_payload: dict[str, Any]
    ) -> InvokeResult:
        if not result_payload.get("ok"):
            error = result_payload.get("error")
            if not error:
                return _failure(
                    invocation_id,
                    ErrorCode.MALFORMED_RESULT,
                    "node returned failure with no error shape",
                )
            return InvokeResult(invocation_id=invocation_id, ok=False, error=error)

        data = result_payload.get("data") or {}
        descriptor = self._descriptors.get(req.device_id or "", {}).get(req.capability)
        if descriptor is not None:
            try:
                validate_output(descriptor, data)
            except SchemaValidationError as exc:
                # `malformed_result` is what the model sees; `schema_drift` is the paired
                # log-only record — this checker can't distinguish "the node is simply
                # misbehaving" from "the advertised schema itself has drifted", so both causes
                # log this same line (hdp-spec/errors.md's `schema_drift` entry).
                logger.warning(
                    "schema_drift capability=%s device_id=%s detail=%s",
                    req.capability,
                    req.device_id,
                    exc,
                )
                return _failure(invocation_id, ErrorCode.MALFORMED_RESULT, str(exc))
        return InvokeResult(invocation_id=invocation_id, ok=True, data=data)

    async def cancel(self, invocation_id: str, reason: str) -> None:
        """Genuinely implemented at M1 (was `raise NotImplementedError` in `inproc.py`) — best
        effort, and safe to call concurrently with an in-flight `invoke()` for the same id: it
        resolves the pending futures with a negative result rather than raising into them, so a
        concurrent awaiter gets an ordinary `InvokeResult`, not an exception.

        No caller reaches this at M1 — `invoke()`'s own ack/deadline timeout handling stays
        internal to itself. This exists so the `BridgeTransport` method is real, for any future
        or manual caller and for direct tests of the transport.
        """
        entry = self._invocations.expire(invocation_id)
        if entry is None:
            return
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

    async def list_devices(self) -> list[DeviceInfo]:
        return self._registry.list_devices()

    async def status(self) -> BridgeStatus:
        return BridgeStatus(
            healthy=True, detail=f"embedded server, {len(self._connections)} device(s) connected"
        )

    async def list_approvals(self) -> list[PendingApproval]:
        raise NotImplementedError("approvals are not implemented until M3")

    async def resolve_approval(self, invocation_id: str, decision: str, scope: str) -> None:
        raise NotImplementedError("resolve_approval is not implemented until M3")
