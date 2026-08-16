"""Operator-initiated revocation (FR-15, §4.4) — immediate and total, four steps in this exact
order: (1) invalidate the credential (committed first — a crash mid-revoke fails closed), (2) send
the `revoke` wire frame to a live connection, (3) close its socket, (4) fail every in-flight
invocation for that device immediately with a `revoked` error code (not `device_offline`).

The order matters: a crash between steps must never leave a revoked device still able to
authenticate. Committing the credential invalidation first (`credentials.revoke_credential`, its
own transaction) means a crash after step 1 still fails closed — the device simply can't
reconnect, even though its live socket briefly outlives the revocation. A crash before step 1
leaves everything untouched (the operator just retries). No ordering of steps 2-4 can produce an
unrevoked-but-live device once step 1 has committed.
"""

from __future__ import annotations

import json
import sqlite3

from hdp_proto.envelope import Envelope

from . import credentials
from .connection import NodeConnection


async def revoke_device(
    conn: sqlite3.Connection,
    device_id: str,
    *,
    connections: dict[str, NodeConnection],
) -> None:
    credentials.revoke_credential(conn, device_id)  # step 1 — committed first, fails closed

    connection = connections.get(device_id)
    if connection is None:
        return  # not currently connected — nothing live to disconnect or fail in-flight

    envelope = Envelope.new("revoke", {"reason": "revoked by operator"})
    try:
        await connection._ws.send_str(json.dumps(envelope.to_wire()))  # step 2
    except (ConnectionResetError, OSError):
        pass

    # Set *before* closing: on a real `aiohttp` WebSocket, `close()` concurrently wakes this
    # connection's own `run()` loop, which reaches `_on_disconnect` and calls
    # `fail_all_for_device` on its own — a race against the explicit step 4 below. Whichever of
    # the two actually pops the pending entries must fail them with `"revoked"`, not the ordinary-
    # disconnect default, so the connection needs to know the reason before the close can trigger
    # that race at all.
    connection._disconnect_reason = "revoked"

    await connection._ws.close(code=4001, message=b"revoked")  # step 3

    connection._invocations.fail_all_for_device(device_id, reason="revoked")  # step 4 — a no-op
    # if `_on_disconnect` (see above) already won the race and popped these entries itself.
