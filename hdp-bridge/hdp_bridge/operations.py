"""Operator-surface orchestration, owned by `hdp_bridge` and shared by both operator CLIs.

`hdp pair new` / `hdp devices revoke` (`hdp_bridge/cli.py`) and `hermes hdp pair
--new` / `hermes hdp devices revoke` (`hermes_device_plugin/cli.py`) are two *renderers* of the
same two operations (FR-18's surface-independence claim). Before this module they were also two
*implementations*: each one separately decided whether a daemon was reachable, separately fell
back to a direct DB revoke, and separately wrote the fallback's audit record — real domain logic
duplicated, not just socket glue, so a fix to one silently missed the other (final-review finding
I5, which is exactly how finding I4's fail-open bug came to exist in two places at once).

The decisions live here now. Both CLIs are thin: `hdp_bridge/cli.py` wraps these in
`asyncio.run()`; `hermes_device_plugin/cli.py`'s already-async command handlers await them
directly (so they keep working inside gateway mode's running loop — NFR-3).

**Global Constraint note.** These functions open `registry.db` and the audit log directly. That
is the plan's one deliberate exception to "the plugin process never opens `registry.db`" — it is
scoped to *operator CLI invocations*, which are short-lived separate processes, and never to the
always-running plugin process. Finding I1 closed the one hole in that scoping: `/hdp pair` and
`/hdp devices revoke` no longer dispatch here from gateway mode (see `commands.py`).
"""

from __future__ import annotations

import asyncio

from hdp_proto.envelope import Envelope

from . import config, credentials
from .audit import AuditWriter
from .control import read_frame, write_frame
from .store import db as store_db


class PairingCodeRemovedError(RuntimeError):
    """Human-readable pairing codes are not part of USB-sentinel enrollment."""


async def pair_new() -> str:
    """Reject the retired human-code flow.

    Pairing now starts only through a physically attached USB bootstrap adapter after fresh local
    owner authorization. Keeping a programmatic code mint would recreate the remote-attack path.
    """
    raise PairingCodeRemovedError(
        "Pair by USB after local owner authorization; pairing codes are disabled."
    )


async def control_request(verb: str, payload: dict) -> Envelope:
    """Make one operator control-plane request without importing the plugin transport."""
    try:
        reader, writer = await asyncio.open_unix_connection(str(config.control_socket_path()))
    except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
        from hdp_proto.errors import ErrorCode, err

        return Envelope.new("error", err(ErrorCode.BRIDGE_UNAVAILABLE, exc)["error"])
    try:
        request = Envelope.new(verb, payload)
        await write_frame(writer, request.to_wire())
        return Envelope.from_wire(await read_frame(reader))
    finally:
        writer.close()


def revoke_failed(message: str) -> bool:
    """True when `revoke()`'s return value describes a failure rather than a completed revoke.

    Both CLI entry points (`hdp_bridge/cli.py`, `hermes_device_plugin/cli.py`) use this to decide
    their process exit code — `revoke()` itself keeps returning a plain string rather than raising,
    since that string is also what each CLI prints verbatim. A caller that only prints the message
    and always exits 0 is fail-open on a security command in exactly the way this module exists to
    prevent (re-review finding I4, round 2); this predicate is what closes that gap.
    """
    return message.startswith(("no such device ", "revoke failed:"))


async def revoke(device_id: str) -> str:
    """Revoke `device_id`, returning the line the caller should render.

    Prefers the control socket: reaching a live daemon means the `revoke` frame is really sent,
    the node's socket really closes, and in-flight invocations really fail (`revocation.py`'s
    four ordered steps). Falls back to a direct DB-only revoke when no daemon answers — there is
    nothing live to disconnect in that case anyway, and the credential must still be invalidated
    so a later daemon start doesn't let the device back in.

    Neither path fails open (finding I4): the daemon's reply type is checked, and the fallback's
    affected-row count is checked. A revoke that changed nothing reports "no such device" and
    writes no audit record — an audit trail should describe what happened, not what was asked.
    """
    reply = await _revoke_via_control_socket(device_id)
    if reply is not None:
        if reply.type != "ctl_devices_revoke_reply":
            return f"revoke failed: {_error_detail(reply)}"
        return f"revoked {device_id}"

    conn = store_db.connect(config.registry_db_path())
    affected = credentials.revoke_credential(conn, device_id)
    if affected == 0:
        return f"no such device {device_id}"
    # `via="offline_fallback"` distinguishes this record from an operator revoke against a live
    # daemon (which `revocation.revoke_device` audits itself) — same event name, same
    # `device_id=...` shape, one extra field.
    AuditWriter(config.hdp_home() / "audit").record(
        "revoked", device_id=device_id, via="offline_fallback"
    )
    return f"revoked {device_id}"


async def _revoke_via_control_socket(device_id: str) -> Envelope | None:
    """Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if no daemon
    is reachable. A reply that arrives but is malformed is *not* treated as unreachable — falling
    back to the DB-only path there would double-revoke against a daemon that is plainly alive; it
    surfaces as a failure instead."""
    try:
        reader, writer = await asyncio.open_unix_connection(str(config.control_socket_path()))
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        return None
    try:
        await write_frame(
            writer, Envelope.new("ctl_devices_revoke", {"device_id": device_id}).to_wire()
        )
        raw = await read_frame(reader)
    finally:
        writer.close()
    return Envelope.from_wire(raw)


def _error_detail(reply: Envelope) -> str:
    message = reply.payload.get("message") or ""
    code = reply.payload.get("code") or reply.type
    return f"{code}: {message}" if message else str(code)
