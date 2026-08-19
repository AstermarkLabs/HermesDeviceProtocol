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
import os
import random
import re
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import aiohttp
from hdp_proto.capabilities import CapabilityDescriptor
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
_DESCRIPTOR_BY_NAME = {descriptor.name: descriptor for descriptor in _DESCRIPTORS}
_CAPABILITY_VERSION_PATTERN = re.compile(r"^(?P<name>[^@]+)@(?P<version>[1-9][0-9]*)$")

_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 30.0
_BACKOFF_JITTER_FRACTION = 0.25
"""FR-14's reconnect schedule, exactly: exponential from 1s to a 30s ceiling, jittered.

The previous shape (`min(30.0, 0.5 * (2 ** (attempt - 1)))`) started at 0.5s and had no jitter at
all, so a bridge restart with N nodes attached produced N reconnect attempts in lockstep, forever
— a self-inflicted thundering herd, and the reason FR-14 says "jittered" rather than merely
"backed off". `hermes_device_plugin/transport/socket.py` already implements this same shape for
the plugin side, describing itself as reusing the node-side one; this is now that shape.
"""


class AuthFailed(Exception):
    """The bridge rejected this node's credential.

    Deliberately **not** an `OSError` subclass. The previous code raised `ConnectionError` here,
    which *is* one — so `run()`'s `except (aiohttp.ClientError, OSError)` reconnect handler caught
    it and retried forever, presenting the same rejected credential every time. A rejected
    credential is not a transient network condition and no amount of retrying will change it, so
    this must be a type that reconnect handling cannot accidentally swallow.
    """


def _write_credential(credential_file: Path, credential: str) -> None:
    """Write the bridge-issued credential 0600, with no world-readable window at any point.

    `Path.write_text` creates at the process umask (typically 0644): a long-lived device secret
    readable by every user on the machine. `os.open` with the mode argument closes that, but only
    for a file that does not already exist — `O_CREAT`'s mode is ignored outright when it does —
    so `fchmod` on the returned descriptor covers the re-pairing case too. Both act on the fd, so
    there is no window and no path-based race. `O_NOFOLLOW` refuses to write through a symlink
    planted at `credential_file`'s path, so a local attacker can't redirect the secret write.
    """
    fd = os.open(credential_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        os.fchmod(fd, 0o600)
        handle.write(credential)


def descriptors_for_overrides(overrides: Sequence[str]) -> tuple[CapabilityDescriptor, ...]:
    """Build the advertised descriptor set for repeatable ``NAME@N`` CLI overrides.

    Each named capability's override versions replace its built-in set. The reference node has
    only v1 implementations, so conformance-only versions intentionally clone that capability's
    v1 schemas and continue to use its name-keyed handler. Production calls this with an empty
    sequence and advertises only the three shipped ``@1`` descriptors.
    """
    versions_by_name: dict[str, set[int]] = {}
    for raw in overrides:
        match = _CAPABILITY_VERSION_PATTERN.fullmatch(raw)
        if match is None:
            raise ValueError(
                f"invalid --capability-version {raw!r}; expected known capability NAME@N "
                "with a positive integer version"
            )
        name = match.group("name")
        descriptor = _DESCRIPTOR_BY_NAME.get(name)
        if descriptor is None:
            raise ValueError(f"unknown capability in --capability-version: {name!r}")
        version = int(match.group("version"))
        versions = versions_by_name.setdefault(name, set())
        if version in versions:
            raise ValueError(f"duplicate --capability-version: {name}@{version}")
        versions.add(version)

    advertised: list[CapabilityDescriptor] = []
    for descriptor in _DESCRIPTORS:
        versions = versions_by_name.get(descriptor.name)
        if versions is None:
            advertised.append(descriptor)
        else:
            advertised.extend(replace(descriptor, version=version) for version in sorted(versions))
    return tuple(advertised)


async def run(
    url: str,
    name: str,
    faults: FaultConfig,
    *,
    pair_code: str | None = None,
    credential: str | None = None,
    credential_file: Path = Path("./.hdp-node-credential"),
    descriptors: tuple[CapabilityDescriptor, ...] = _DESCRIPTORS,
    max_reconnect_attempts: int | None = None,
) -> None:
    """Connect, advertise, dispatch forever, reconnecting with exponential backoff on an
    unexpected disconnect. A clean server-initiated close (the bridge's own WS close, not a
    network error) ends `run` rather than triggering a reconnect — the caller decides whether to
    call `run` again. `max_reconnect_attempts` is `None` for the real CLI (retry forever); tests
    pass a small number so a deliberately uncooperative bridge cannot hang a test suite.

    M2 auth (hdp-spec/HDP-0.md's Amendments (v0.2)): an explicit `credential` is process-local
    and bypasses `credential_file` for both reads and writes (M4 D6's multi-node escape hatch).
    Otherwise `credential_file` is checked first on every connect attempt, including reconnects.
    If it already holds a stored credential, that credential is sent as-is and `pair_code` is
    ignored. Only when no stored credential exists is `pair_code` used, prefixed `pair:`, to
    complete a first-time pairing; the credential issued in response is written immediately so
    every subsequent reconnect uses it instead of the consumed one-time pairing code.

    Two M2 conditions end `run` for good rather than reconnecting, because reconnecting could
    only present a credential the bridge has already refused: an `auth_failed` close during the
    handshake (raised as `AuthFailed`, which is *not* an `OSError` and so is not caught by the
    reconnect handler below), and a `revoke` frame on an established session (which returns
    cleanly out of `_connect_and_serve`).
    """
    attempt = 0
    while max_reconnect_attempts is None or attempt < max_reconnect_attempts:
        try:
            await _connect_and_serve(
                url,
                name,
                faults,
                pair_code,
                credential,
                credential_file,
                descriptors,
            )
            return
        except AuthFailed as exc:
            # Terminal, never retried: the credential this node holds is not one the bridge will
            # accept (revoked, unknown, or an expired/consumed pairing code). Reconnecting can
            # only present the same rejected credential again (FR-15's revocation is meant to be
            # immediate and total, so a node that retried through it would be defeating it).
            logger.error("authentication rejected by the bridge (%s); not reconnecting", exc)
            raise
        except (aiohttp.ClientError, OSError) as exc:
            attempt += 1
            if max_reconnect_attempts is not None and attempt >= max_reconnect_attempts:
                raise
            backoff = _backoff_delay(attempt)
            logger.warning("connection lost (%s), reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)


def _backoff_delay(attempt: int) -> float:
    """FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based.

    The 30s ceiling applies to `base` (the exponential term) only, not to `base + jitter` — an
    earlier version clamped the final sum too, which meant every attempt at the ceiling returned
    exactly `_MAX_BACKOFF_S`, nullifying jitter at steady state (the exact thundering-herd
    condition this backoff exists to prevent — re-review finding, round 2). `transport/socket.py`
    already gets this right: its ceiling is on `_backoff_s` before adding jitter, not on the
    result.
    """
    base = min(_MAX_BACKOFF_S, _INITIAL_BACKOFF_S * (2 ** (attempt - 1)))
    jitter = random.uniform(0, base * _BACKOFF_JITTER_FRACTION)  # noqa: S311
    # Not a security context — retry-storm jitter for a reconnect loop, not a cryptographic
    # value. Same call, same reasoning, as `transport/socket.py`'s plugin-side backoff.
    return base + jitter


def _resolve_credential(
    pair_code: str | None, credential: str | None, credential_file: Path
) -> str:
    if credential is not None:
        if not credential:
            raise SystemExit("--credential must not be empty")
        return credential
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
    url: str,
    name: str,
    faults: FaultConfig,
    pair_code: str | None,
    credential: str | None,
    credential_file: Path,
    descriptors: tuple[CapabilityDescriptor, ...],
) -> None:
    resolved_credential = _resolve_credential(pair_code, credential, credential_file)
    async with aiohttp.ClientSession() as session, session.ws_connect(url, heartbeat=15.0) as ws:
        hello = Hello(
            hdp_versions=(0,),
            device_name=name,
            capabilities=descriptors,
            credential=resolved_credential,
        )
        await ws.send_str(json.dumps(Envelope.new("hello", hello.to_wire()).to_wire()))

        welcome_msg = await ws.receive()
        if welcome_msg.type != aiohttp.WSMsgType.TEXT:
            # The bridge closes with `POLICY_VIOLATION` (1008) and no reply frame on every
            # `auth_failed` path — no credential, unknown credential, invalid/expired pairing
            # code (see `hdp_bridge/connection.py`'s `_handle_hello`). That is categorically
            # different from a dropped socket and must not be retried. Note 4001 is *revocation*
            # of an already-established session, handled on the frame path below, not here.
            if ws.close_code == aiohttp.WSCloseCode.POLICY_VIOLATION:
                raise AuthFailed("the bridge rejected this node's credential")
            raise ConnectionError(f"expected a welcome frame, got {welcome_msg.type!r}")
        welcome_envelope = Envelope.from_wire(json.loads(welcome_msg.data))
        if welcome_envelope.type != "welcome":
            raise ConnectionError(f"expected welcome, got {welcome_envelope.type!r}")
        welcome = Welcome.from_wire(welcome_envelope.payload)
        logger.info("connected as device_id=%s", welcome.device_id)
        if welcome.credential is not None and credential is None:
            # First-time pairing just completed — persist the newly-issued credential so every
            # future connect (this run's own reconnects, and any later invocation of this CLI
            # against the same --credential-file) authenticates as a returning device instead.
            _write_credential(credential_file, welcome.credential)

        node_session = _NodeSession(ws, faults)
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await node_session.handle_frame(msg.data)
                if node_session.revoked:
                    # Returning normally (rather than raising) is what stops `run()` from
                    # reconnecting — the credential we hold is now dead, so a reconnect would
                    # only earn an `auth_failed` close. FR-15's revocation is immediate and
                    # total; the node's job is to stay gone.
                    return
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
        self.revoked = False
        """Set once a `revoke` frame arrives — `_connect_and_serve` reads it to end the session
        for good rather than reconnecting."""

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
        elif envelope.type == "revoke":
            await self._handle_revoke(envelope)
        # welcome/ack/error: nothing for this reference implementation to do.

    async def _handle_revoke(self, envelope: Envelope) -> None:
        """M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a wire
        type nothing ever emitted, which is why this used to be a no-op.

        An operator has invalidated this device's credential. Log it loudly (this is the one
        message that explains to whoever is reading the node's output why it just stopped), close
        the connection, and let `_connect_and_serve` return so `run()` does not reconnect with a
        credential the bridge will now reject.
        """
        reason = envelope.payload.get("reason", "")
        logger.error("revoked by the bridge (%s); disconnecting and not reconnecting", reason)
        self.revoked = True
        await self._ws.close()

    def _handle_cancel(self, envelope: Envelope) -> None:
        if envelope.corr:
            self._cancelled.add(envelope.corr)

    async def _handle_invoke(self, envelope: Envelope) -> None:
        invocation_id = envelope.corr
        capability = envelope.payload.get("capability")
        version = envelope.payload.get("version")
        args = envelope.payload.get("args", {})
        logger.info(
            "received invoke invocation_id=%s capability=%s version=%s",
            invocation_id,
            capability,
            version,
        )

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
                    "code": "policy_denied",
                    "message": f"local policy denies {capability!r}",
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
