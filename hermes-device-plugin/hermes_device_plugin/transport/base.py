"""`BridgeTransport` — the ADR-0004 extraction seam.

`engine.py` depends on this `Protocol` and never on a concrete server or connection object. At
M0/M1 `inproc.py` implements it as an in-process loopback stub; at M2 `socket.py` implements it
as a Unix-socket client to the extracted `hdp-bridge` daemon. Flipping one factory in
`runtime.py` swaps the implementation — `engine.py`, `tools.py`, `schemas.py`, and every CLI/
slash-command surface are untouched (design §2.2).

All request/response types live here too, so both implementations (and their tests) share one
shape. These are plain dataclasses, not pydantic (SDR-3) — this package is imported by the
Hermes-hosted plugin, so it inherits `hdp_proto`'s stdlib-only constraint transitively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class InvokeRequest:
    """One capability invocation, fully resolved by `engine.py` before it reaches the transport.

    Carries no `invocation_id`: that id is **bridge-minted** (FR-28), and at M0/M1 the loopback
    stub *is* the bridge, so the mint happens inside `transport.invoke()`, not here. Keeping the
    mint on the transport side of the seam from day one is what stops a future engine.py change
    from accidentally taking over minting when M2 moves the bridge to a real process.
    """

    capability: str
    version: int
    device_id: str | None
    args: dict[str, Any]
    deadline_ms: int
    meta: dict[str, Any] = field(default_factory=dict)
    """Hermes task/session metadata, carried opaquely (seed §17, FR-28) — never consulted by the
    transport or the engine for correctness."""


@dataclass(frozen=True)
class InvokeResult:
    """The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is set."""

    invocation_id: str
    ok: bool
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class CapabilityInfo:
    name: str
    version: int


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    friendly_name: str
    platform: str
    online: bool
    capabilities: list[CapabilityInfo] = field(default_factory=list)


@dataclass(frozen=True)
class BridgeStatus:
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class PendingApproval:
    """An HDP `pending_approval` state (seed §17). Unreachable at M0 — the stub never returns
    ASK — declared here so M3 fills a known shape rather than inventing one."""

    invocation_id: str
    device_id: str
    capability: str
    version: int
    args_summary: str
    requesting_session: str
    risk_class: str
    created_at: int
    expires_at: int


class BridgeTransport(Protocol):
    """The eight operations `engine.py` and the plugin's diagnostics/status surface need from
    whatever is on the other side of the seam — an in-process stub today, a daemon at M2+."""

    async def invoke(self, req: InvokeRequest) -> InvokeResult: ...
    async def cancel(self, invocation_id: str, reason: str) -> None: ...
    async def list_devices(self) -> list[DeviceInfo]: ...
    async def status(self) -> BridgeStatus: ...
    async def list_approvals(self) -> list[PendingApproval]: ...
    async def resolve_approval(self, invocation_id: str, decision: str, scope: str) -> None: ...
    async def start(self) -> None: ...
    async def close(self) -> None: ...
