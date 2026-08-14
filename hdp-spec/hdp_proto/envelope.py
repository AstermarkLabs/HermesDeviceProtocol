"""The HDP/0 envelope: `{"hdp", "type", "id", "ts", "corr", "payload"}` — see field rules below.

Hand-written `from_wire`/`to_wire`, no pydantic (SDR-3) and no `cls(**d)` splat — see
`EnvelopeError` and the discipline notes on `from_wire` below. `hdp_proto` is stdlib-only and
imported by both the plugin (Hermes's interpreter) and, from M2, the standalone bridge daemon;
a single shared codec is what keeps that split a `git mv` rather than a fork (ADR-0004).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from hdp_proto import ids
from hdp_proto.version import HDP_VERSION, KNOWN_TYPES


class EnvelopeError(ValueError):
    """Raised by `Envelope.from_wire` on any structurally or semantically invalid frame.

    The one failure mode of this codec. Callers must handle it explicitly; `from_wire` never
    returns `None` on invalid input (docs/m0-plan.md §4.1) — a `None`-on-invalid contract is the
    shape that gets `if env:`-checked and dereferenced two lines later.
    """


@dataclass(frozen=True)
class Envelope:
    """An HDP/0 frame. `payload` is opaque to this layer — Hermes `task_id`/`session_id` ride
    inside it as metadata only, so envelope validation never reaches into `payload` and HDP
    correctness never depends on Hermes internals (seed §17, FR-28)."""

    type: str
    id: str
    ts: int
    payload: dict[str, Any]
    corr: str | None = None

    @classmethod
    def new(cls, type: str, payload: dict[str, Any], *, corr: str | None = None) -> Envelope:
        """Mint a fresh envelope: new ULID `id`, current-time `ts`. Convenience for senders;
        `from_wire` is the only path that constructs an `Envelope` from untrusted input."""
        return cls(type=type, id=ids.new(), ts=int(time.time() * 1000), payload=payload, corr=corr)

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Envelope:
        """Validate and construct. Never `cls(**d)` — an unknown top-level key must not become a
        `TypeError`, and reading fields by name is what makes "unknown fields are tolerated" a
        decision (see §4.2 below) rather than an accident of the dataclass's constructor.
        """
        if not isinstance(d, dict):
            raise EnvelopeError(f"envelope must be a JSON object, got {type(d).__name__}")

        hdp = d.get("hdp")
        if hdp != HDP_VERSION:
            # A version we do not speak is closed before any further processing — deliberately
            # checked first, before there is anything else (e.g. auth) to skip (m1-plan §3.3).
            raise EnvelopeError(f"unsupported hdp version: {hdp!r}")

        msg_type = d.get("type")
        if not isinstance(msg_type, str) or msg_type not in KNOWN_TYPES:
            # Unknown *type* is a rejection; unknown *fields* within a known type are not
            # (§4.2's tolerance rule, transcribed into HDP-0.md as normative at M1).
            raise EnvelopeError(f"unknown or missing envelope type: {msg_type!r}")

        frame_id = d.get("id")
        if not isinstance(frame_id, str) or not ids.is_valid(frame_id):
            raise EnvelopeError(f"invalid envelope id: {frame_id!r}")

        ts = d.get("ts")
        if not isinstance(ts, int) or isinstance(ts, bool):
            raise EnvelopeError(f"invalid envelope ts: {ts!r}")

        payload = d.get("payload")
        if not isinstance(payload, dict):
            raise EnvelopeError(f"invalid envelope payload: {type(payload).__name__}")

        corr = d.get("corr")
        if corr is not None and not isinstance(corr, str):
            raise EnvelopeError(f"invalid envelope corr: {corr!r}")

        # Fields are read by name above; anything else in `d` is silently ignored — additive
        # wire changes never require every receiver to upgrade in lockstep (§4.2).
        return cls(type=msg_type, id=frame_id, ts=ts, payload=payload, corr=corr)

    def to_wire(self) -> dict[str, Any]:
        """Return a plain `dict`, never a string — serialization belongs to the transport layer,
        which at M0 is a function call with no serialization at all."""
        return {
            "hdp": HDP_VERSION,
            "type": self.type,
            "id": self.id,
            "ts": self.ts,
            "corr": self.corr,
            "payload": self.payload,
        }
