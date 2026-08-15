"""HDP wire version and the known-message-type boundary.

The full HDP/0 type set, per `hdp-spec/HDP-0.md` §2: Node→Bridge (`hello`, `capabilities`,
`ack`, `result`, `progress`, `heartbeat`, `error`) and Bridge→Node (`welcome`, `invoke`, `cancel`,
`ack`, `revoke`, `heartbeat`, `error`), deduplicated into one set — the same envelope and type
names are reused for the plugin↔bridge control plane too (ADR-0004), so a single receiver-side
set covers both directions and both planes.

The boundary this module exists to state: a receiver rejects an unknown *type* with an `error`
reply (or refuses the connection, for the version itself); it must never reject an unknown
*field* within a known type. That second half lives in `envelope.py`'s `from_wire`.
"""

from __future__ import annotations

HDP_VERSION = "0"
"""The literal value of the envelope's `hdp` field. A different value is a rejection, not a
best-effort parse — see envelope.py `from_wire`."""

KNOWN_TYPES = frozenset(
    {
        "hello",
        "welcome",
        "capabilities",
        "invoke",
        "cancel",
        "ack",
        "result",
        "progress",
        "revoke",
        "heartbeat",
        "error",
    }
)
"""The full HDP/0 message-type set (hdp-spec/HDP-0.md §2). `progress` and `revoke` are declared
but have no producer or consumer at M1 — see HDP-0.md §2's note on why they're defined early."""
