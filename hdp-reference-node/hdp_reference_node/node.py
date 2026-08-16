"""The reference node: connects to an HDP bridge over WebSocket, advertises its three
capabilities, and dispatches invocations to their handlers.

`FaultConfig` (faults.py) lets the node deliberately misbehave at each step the conformance suite
needs to prove a failure path against — driven entirely through the CLI, never by a test
importing this module and monkeypatching it (M1-4's review rule, m1-plan.md §9).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp
from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.messages import Hello, ResultMsg, Welcome

from . import local_policy
from .capabilities import device_status, diagnostics, notifications
from .faults import FaultConfig

logger = logging.getLogger(__name__)

_DESCRIPTORS = (notifications.DESCRIPTOR, diagnostics.DESCRIPTOR, device_status.DESCRIPTOR)
_HANDLERS = {
    notifications.DESCRIPTOR.name: notifications.handle,
    diagnostics.DESCRIPTOR.name: diagnostics.handle,
    device_status.DESCRIPTOR.name: device_status.handle,
}

_MAX_BACKOFF_S = 30.0


async def run(
    url: str,
    name: str,
    faults: FaultConfig,
    *,
    pair_code: str | None = None,
    credential_file: Path = Path("./.hdp-node-credential"),
    max_reconnect_attempts: int | None = None,
) -> None:
    """Connect, advertise, dispatch forever, reconnecting with exponential backoff on an
    unexpected disconnect. A clean server-initiated close (the bridge's own WS close, not a
    network error) ends `run` rather than triggering a reconnect — the caller decides whether to
    call `run` again. `max_reconnect_attempts` is `None` for the real CLI (retry forever); tests
    pass a small number so a deliberately uncooperative bridge cannot hang a test suite.

    M2 auth (hdp-spec/HDP-0.md's Amendments (v0.2)): `credential_file` is checked first on every
    connect attempt, including reconnects — if it already holds a stored credential (from a
    previous pairing, on this run or an earlier one), that credential is sent as-is and
    `pair_code` is ignored. Only when no stored credential exists is `pair_code` used, prefixed
    `pair:`, to complete a first-time pairing; the credential the bridge issues in response is
    written to `credential_file` immediately so every subsequent reconnect in this `run()` call
    (and every future invocation of this CLI against the same `--credential-file`) uses it
    instead of the one-time pairing code, which the bridge has already consumed.
    """
    attempt = 0
    while max_reconnect_attempts is None or attempt < max_reconnect_attempts:
        try:
            await _connect_and_serve(url, name, faults, pair_code, credential_file)
            return
        except (aiohttp.ClientError, OSError) as exc:
            attempt += 1
            if max_reconnect_attempts is not None and attempt >= max_reconnect_attempts:
                raise
            backoff = min(_MAX_BACKOFF_S, 0.5 * (2 ** (attempt - 1)))
            logger.warning("connection lost (%s), reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)


def _resolve_credential(pair_code: str | None, credential_file: Path) -> str:
    if credential_file.exists():
        stored = credential_file.read_text().strip()
        if stored:
            return stored
    if pair_code:
        return f"pair:{pair_code}"
    raise SystemExit(
        f"no stored credential at {credential_file} and no --pair-code given; "
        "a node's first connection requires one or the other"
    )


async def _connect_and_serve(
    url: str, name: str, faults: FaultConfig, pair_code: str | None, credential_file: Path
) -> None:
    credential = _resolve_credential(pair_code, credential_file)
    async with aiohttp.ClientSession() as session, session.ws_connect(url, heartbeat=15.0) as ws:
        hello = Hello(
            hdp_versions=(0,), device_name=name, capabilities=_DESCRIPTORS, credential=credential
        )
        await ws.send_str(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))

        welcome_msg = await ws.receive()
        if welcome_msg.type != aiohttp.WSMsgType.TEXT:
            raise ConnectionError(f"expected a welcome frame, got {welcome_msg.type!r}")
        welcome_envelope = Envelope.from_wire(json.loads(welcome_msg.data))
        if welcome_envelope.type != "welcome":
            raise ConnectionError(f"expected welcome, got {welcome_envelope.type!r}")
        welcome = Welcome.from_wire(welcome_envelope.payload)
        logger.info("connected as device_id=%s", welcome.device_id)
        if welcome.credential is not None:
            # First-time pairing just completed — persist the newly-issued credential so every
            # future connect (this run's own reconnects, and any later invocation of this CLI
            # against the same --credential-file) authenticates as a returning device instead.
            credential_file.write_text(welcome.credential)

        node_session = _NodeSession(ws, faults)
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await node_session.handle_frame(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break


class _NodeSession:
    """Per-connection dispatch state: which invocation ids have been cancelled by the bridge, so
    a subsequent (possibly `slow-result`-delayed) result can honor that cancellation — unless
    `faults.ignore_cancel` says this node should behave like an uncooperative one."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse, faults: FaultConfig) -> None:
        self._ws = ws
        self._faults = faults
        self._cancelled: set[str] = set()

    async def handle_frame(self, raw: str) -> None:
        try:
            data = json.loads(raw)
            envelope = Envelope.from_wire(data)
        except (ValueError, EnvelopeError):
            return  # a malformed frame from the bridge is not this reference node's problem

        if envelope.type == "invoke":
            await self._handle_invoke(envelope)
        elif envelope.type == "cancel":
            self._handle_cancel(envelope)
        elif envelope.type == "heartbeat":
            await self._send(Envelope.new("heartbeat", {}))
        # welcome/ack/revoke/error: no action needed from this reference implementation at M1.

    def _handle_cancel(self, envelope: Envelope) -> None:
        if envelope.corr:
            self._cancelled.add(envelope.corr)

    async def _handle_invoke(self, envelope: Envelope) -> None:
        invocation_id = envelope.corr
        capability = envelope.payload.get("capability")
        args = envelope.payload.get("args", {})

        if self._faults.drop_connection_mid_call:
            await self._ws.close()
            return

        if not self._faults.never_ack:
            await self._send(Envelope.new("ack", {}, corr=invocation_id))

        if self._faults.slow_result_ms:
            await asyncio.sleep(self._faults.slow_result_ms / 1000)

        if invocation_id and invocation_id in self._cancelled and not self._faults.ignore_cancel:
            self._cancelled.discard(invocation_id)
            return  # honored the cancel — no result sent

        result = await self._build_result(capability, args)
        envelope_out = Envelope.new("result", result.to_wire(), corr=invocation_id)
        await self._send(envelope_out)
        if self._faults.duplicate_result:
            # Re-send the *same* envelope (identical `id`) — exercises the envelope-id dedupe
            # backstop on top of the pending-table's own pop-once semantics.
            await self._send(envelope_out)

    async def _build_result(self, capability: str | None, args: dict[str, Any]) -> ResultMsg:
        if capability is None or not local_policy.is_allowed(capability):
            return ResultMsg(
                ok=False,
                data=None,
                error={
                    "code": "capability_unsupported",
                    "message": f"no local handler for {capability!r}",
                    "hint": "",
                },
            )
        handler = _HANDLERS[capability]
        data = await handler(args)
        if self._faults.malformed_result or self._faults.stale_schema:
            data = {"deliberately_wrong_field": "the output schema requires other fields"}
        return ResultMsg(ok=True, data=data, error=None)

    async def _send(self, envelope: Envelope) -> None:
        await self._ws.send_str(json.dumps(envelope.to_wire()))
