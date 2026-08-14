"""HDP wire version and the known-message-type boundary.

M0 contents only: the wire constant, and the type set the M0 loopback transport actually needs
to round-trip an envelope (`invoke`, `result`, `error`). M1 replaces `KNOWN_TYPES` with the full
type set defined in `hdp-spec/HDP-0.md` — `hello`, `welcome`, `advertise`, `cancel`, `ack`, etc.

The boundary this module exists to state: a receiver rejects an unknown *type* with an `error`
reply (or refuses the connection, for the version itself); it must never reject an unknown
*field* within a known type. That second half lives in `envelope.py`'s `from_wire`.
"""

from __future__ import annotations

HDP_VERSION = "0"
"""The literal value of the envelope's `hdp` field. A different value is a rejection, not a
best-effort parse — see envelope.py `from_wire`."""

KNOWN_TYPES = frozenset({"invoke", "result", "error"})
"""Message types M0's loopback transport can emit or accept. Extended to the full HDP/0 type set
at M1 (see hdp-spec/HDP-0.md)."""
