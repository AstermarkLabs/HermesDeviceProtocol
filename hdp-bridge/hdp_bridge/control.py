"""Plugin↔bridge Unix-socket control plane (ADR-0004, HDP-0.md §2's "same envelope, same type
names" claim reused for a private type-name vocabulary — see this plan's Global Constraints for
the exact verb set). Length-prefixed JSON frames: 4-byte big-endian length, then that many bytes
of one JSON object.

Only `ctl_list_devices` is dispatched at this task (Task 5) — the remaining five
plugin-reachable verbs (`ctl_invoke`, `ctl_cancel`, `ctl_status`, `ctl_list_approvals`,
`ctl_resolve_approval`) land in Task 6 alongside the client that calls them, one verb per TDD
cycle. An unrecognized-but-known-wire-type verb (including those five, until their task lands)
falls through `_dispatch`'s `handler is None` branch and gets `not_implemented`, not a crash.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.errors import ErrorCode, err

if TYPE_CHECKING:
    from .connection import NodeConnection
    from .invocations import InvocationsMem
    from .registry import RegistryMem

logger = logging.getLogger(__name__)

_MAX_FRAME_BYTES = 16 * 1024 * 1024
_REJECTED_VERBS = frozenset({"ctl_policy_set", "ctl_pair_mint"})


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
    ) -> None:
        self._socket_path = socket_path
        self._registry = registry
        self._invocations = invocations
        self._connections = connections
        self._server: asyncio.Server | None = None

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
            writer.close()

    async def _dispatch(self, envelope: Envelope) -> Envelope:
        if envelope.type in _REJECTED_VERBS:
            logger.warning("rejected control verb=%s (audited)", envelope.type)
            detail = f"{envelope.type} is not accepted on this connection"
            error_payload = err(ErrorCode.AUTH_FAILED, detail)["error"]
            return Envelope.new("error", error_payload)
        handler = {
            "ctl_list_devices": self._ctl_list_devices,
        }.get(envelope.type)
        if handler is None:
            detail = f"unknown control verb {envelope.type!r}"
            error_payload = err(ErrorCode.NOT_IMPLEMENTED, detail)["error"]
            return Envelope.new("error", error_payload)
        return await handler(envelope)

    async def _ctl_list_devices(self, envelope: Envelope) -> Envelope:
        devices = [d.to_wire() for d in self._registry.list_devices()]
        return Envelope.new("ctl_list_devices_reply", {"devices": devices})
