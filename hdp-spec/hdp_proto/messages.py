"""Typed payload dataclasses for each HDP/0 message type (hdp-spec/HDP-0.md §2).

`Envelope` (envelope.py) carries `payload` as an opaque `dict` — these dataclasses are the typed
view of that dict for each `type`, built the same way `Envelope` itself is: frozen, `from_wire`
reads fields by name (never `cls(**d)`), unknown fields tolerated, `to_wire` returns a plain
dict. A caller goes `Envelope.from_wire(raw)` first (validates the envelope shell), then
`SomeMessage.from_wire(envelope.payload)` (validates that type's payload) — the two layers don't
duplicate each other's checks.

`ProgressMsg` and `RevokeMsg` are declared for completeness (HDP-0.md §2 defines both types) even
though neither has an M1 producer or consumer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hdp_proto.capabilities import CapabilityDescriptor


def _require_str(d: dict[str, Any], key: str) -> str:
    value = d.get(key)
    if not isinstance(value, str):
        raise ValueError(f"invalid or missing {key!r}: {value!r}")
    return value


def _require_str_or_none(d: dict[str, Any], key: str) -> str | None:
    value = d.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"invalid {key!r}: {value!r}")
    return value


def _require_dict(d: dict[str, Any], key: str) -> dict[str, Any]:
    value = d.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"invalid or missing {key!r}: {type(value).__name__}")
    return value


def _require_int(d: dict[str, Any], key: str) -> int:
    value = d.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"invalid or missing {key!r}: {value!r}")
    return value


def _capabilities_from_wire(raw: Any) -> tuple[CapabilityDescriptor, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"invalid capabilities list: {type(raw).__name__}")
    return tuple(CapabilityDescriptor.from_wire(item) for item in raw)


@dataclass(frozen=True)
class Hello:
    """Node → Bridge, first frame on a new connection. `hello` doubles as the node's initial
    `capabilities` message (HDP-0.md §3) — a node need not send both.

    `platform` (Amendments v0.3) is an optional self-reported platform identifier, e.g.
    `"android"` or `"linux"`. It is advisory metadata for operator-facing device listings, never
    an authorization input. Absent means the bridge records `"unknown"`, which is what every
    pre-v0.3 node produces — defaulted here so this stays an addition, not a wire break.

    `device_pubkey` (Amendments v0.4) is an optional base64 DER SubjectPublicKeyInfo for the
    node's EC P-256 key. Present on a pairing `hello`, it opts the handshake into the
    challenge-response exchange; the bridge binds the key to the new `device_id` only after the
    node proves possession of the private half. This layer treats it as an opaque string — the
    codec is stdlib-only and does no crypto."""

    hdp_versions: tuple[int, ...]
    device_name: str
    capabilities: tuple[CapabilityDescriptor, ...]
    credential: str | None = None
    platform: str | None = None
    device_pubkey: str | None = None

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Hello:
        versions = d.get("hdp_versions")
        if not isinstance(versions, list) or not all(isinstance(v, int) for v in versions):
            raise ValueError(f"invalid hdp_versions: {versions!r}")
        return cls(
            hdp_versions=tuple(versions),
            device_name=_require_str(d, "device_name"),
            capabilities=_capabilities_from_wire(d.get("capabilities", [])),
            credential=_require_str_or_none(d, "credential"),
            platform=_require_str_or_none(d, "platform"),
            device_pubkey=_require_str_or_none(d, "device_pubkey"),
        )

    def to_wire(self) -> dict[str, Any]:
        return {
            "hdp_versions": list(self.hdp_versions),
            "device_name": self.device_name,
            "capabilities": [c.to_wire() for c in self.capabilities],
            "credential": self.credential,
            "platform": self.platform,
            "device_pubkey": self.device_pubkey,
        }


@dataclass(frozen=True)
class Welcome:
    """Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is present only on
    a first-time pairing handshake, carrying the newly-issued device credential in plaintext
    exactly once; absent (null) on every other `welcome`. Defaulted so this is not a wire break
    for an M1 receiver."""

    hdp_version: int
    device_id: str
    credential: str | None = None

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Welcome:
        return cls(
            hdp_version=_require_int(d, "hdp_version"),
            device_id=_require_str(d, "device_id"),
            credential=_require_str_or_none(d, "credential"),
        )

    def to_wire(self) -> dict[str, Any]:
        return {
            "hdp_version": self.hdp_version,
            "device_id": self.device_id,
            "credential": self.credential,
        }


@dataclass(frozen=True)
class CapabilitiesMsg:
    """Either direction's `capabilities` frame: a full-set replacement, never a delta (FR-8)."""

    capabilities: tuple[CapabilityDescriptor, ...]

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> CapabilitiesMsg:
        return cls(capabilities=_capabilities_from_wire(d.get("capabilities", [])))

    def to_wire(self) -> dict[str, Any]:
        return {"capabilities": [c.to_wire() for c in self.capabilities]}


@dataclass(frozen=True)
class InvokeMsg:
    """Bridge → Node. `corr` (on the envelope, not here) carries the bridge-minted
    `invocation_id`."""

    capability: str
    version: int
    args: dict[str, Any]
    deadline_ms: int

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> InvokeMsg:
        return cls(
            capability=_require_str(d, "capability"),
            version=_require_int(d, "version"),
            args=_require_dict(d, "args"),
            deadline_ms=_require_int(d, "deadline_ms"),
        )

    def to_wire(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "version": self.version,
            "args": self.args,
            "deadline_ms": self.deadline_ms,
        }


@dataclass(frozen=True)
class Ack:
    """Either direction's `ack` frame. Empty payload — the envelope's `corr` carries all the
    information an ack needs."""

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Ack:
        return cls()

    def to_wire(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class ResultMsg:
    """Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like
    `hdp_proto.errors.Error.to_dict()`'s output — but this layer does not import `errors.py` to
    avoid a payload-validation module depending on the model-facing error taxonomy; the bridge is
    responsible for that translation."""

    ok: bool
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> ResultMsg:
        ok = d.get("ok")
        if not isinstance(ok, bool):
            raise ValueError(f"invalid or missing ok: {ok!r}")
        data = d.get("data")
        if data is not None and not isinstance(data, dict):
            raise ValueError(f"invalid data: {type(data).__name__}")
        error = d.get("error")
        if error is not None and not isinstance(error, dict):
            raise ValueError(f"invalid error: {type(error).__name__}")
        return cls(ok=ok, data=data, error=error)

    def to_wire(self) -> dict[str, Any]:
        return {"ok": self.ok, "data": self.data, "error": self.error}


@dataclass(frozen=True)
class CancelMsg:
    """Bridge → Node, sent best-effort on timeout or explicit cancellation."""

    reason: str

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> CancelMsg:
        return cls(reason=_require_str(d, "reason"))

    def to_wire(self) -> dict[str, Any]:
        return {"reason": self.reason}


@dataclass(frozen=True)
class ProgressMsg:
    """Node → Bridge. Declared per HDP-0.md §2; no M1 producer or consumer."""

    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> ProgressMsg:
        return cls(detail=_require_dict(d, "detail") if "detail" in d else {})

    def to_wire(self) -> dict[str, Any]:
        return {"detail": self.detail}


@dataclass(frozen=True)
class Heartbeat:
    """Either direction. Application-level heartbeat, belt-and-suspenders on top of the
    WebSocket layer's own ping/pong (HDP-0.md §4)."""

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Heartbeat:
        return cls()

    def to_wire(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class Challenge:
    """Bridge → Node (Amendments v0.4). A fresh nonce the node must sign to prove it holds the
    private key it enrolled with. Sent after a `hello` that carries a `device_pubkey` (pairing) or
    resolves to a device with a stored key (reconnect), and always before `welcome`."""

    nonce: str

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Challenge:
        return cls(nonce=_require_str(d, "nonce"))

    def to_wire(self) -> dict[str, Any]:
        return {"nonce": self.nonce}


@dataclass(frozen=True)
class Proof:
    """Node → Bridge (Amendments v0.4). Base64 DER ECDSA-P256-SHA256 signature over the
    context-prefixed challenge nonce. The context prefix differs between pairing and reconnect so
    an enrollment signature cannot be replayed as an authentication one."""

    signature: str

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> Proof:
        return cls(signature=_require_str(d, "signature"))

    def to_wire(self) -> dict[str, Any]:
        return {"signature": self.signature}


@dataclass(frozen=True)
class ErrorMsg:
    """Either direction. Same shape `hdp_proto.errors.err()` produces for the model-facing result
    envelope (HDP-0.md §9) — `code`/`message`/`hint` as plain strings, not an `ErrorCode` member,
    since this layer does not import the error taxonomy (see `ResultMsg`'s docstring)."""

    code: str
    message: str
    hint: str

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> ErrorMsg:
        return cls(
            code=_require_str(d, "code"),
            message=_require_str(d, "message"),
            hint=_require_str(d, "hint"),
        )

    def to_wire(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "hint": self.hint}


@dataclass(frozen=True)
class RevokeMsg:
    """Bridge → Node. Declared per HDP-0.md §3.3; unused until M2's credential-revocation work."""

    reason: str

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> RevokeMsg:
        return cls(reason=_require_str(d, "reason"))

    def to_wire(self) -> dict[str, Any]:
        return {"reason": self.reason}
