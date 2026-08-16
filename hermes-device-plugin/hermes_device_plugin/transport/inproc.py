"""The M0/M1 loopback `BridgeTransport`: no server, no socket, no node.

This isolates the loop-ownership question (M0's actual risk, ADR-0002) from the protocol
question. `invoke()` round-trips a real `hdp_proto.Envelope` — so the codec is exercised even
though nothing serializes it to bytes — and returns a canned success, because M0 has no node to
produce a real one. `docs/m0-plan.md` §6.4 and §M0-5 name this precisely: a red M0 test means
"the loop pattern doesn't hold," never "the wire is wrong," because there is no wire yet.

Retained after M1 as a fast, dependency-free test transport (design §2's module docstring) —
this class does not go away when `socket.py` ships.

M2's Task 3 `git mv`'d the shared `transport/_invocations.py` and `transport/_registry_mem.py`
into `hdp_bridge` (they grew real ack/deadline/cancel semantics there — ack-timeout distinct from
execution-deadline, `fail_all_for_device`, etc. — none of which this stub needs or may depend on:
`hermes_device_plugin` must never import `hdp_bridge`, per this plan's Global Constraints). This
stub only ever needed "mint an id" and "list zero devices," so those two tiny pieces are kept
local here instead of reintroducing a shared module this class has no business depending on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hdp_proto import ids
from hdp_proto.envelope import Envelope

from .base import (
    BridgeStatus,
    DeviceInfo,
    InvokeRequest,
    InvokeResult,
    PendingApproval,
)


@dataclass
class _LoopbackInvocations:
    """Minimal id-minting stand-in for the real bridge-side pending-invocation table
    (`hdp_bridge.invocations.InvocationsMem`) — this stub has no node, so nothing ever actually
    waits on an invocation; it only needs a fresh id per call."""

    _pending: set[str] = field(default_factory=set)

    def mint_for(self, device_id: str, *, capability: str = "") -> tuple[str, None]:
        invocation_id = ids.new()
        self._pending.add(invocation_id)
        return invocation_id, None

    def expire(self, invocation_id: str) -> None:
        self._pending.discard(invocation_id)


@dataclass
class _LoopbackRegistry:
    """Minimal stand-in for the real bridge-side device registry (`hdp_bridge.registry.RegistryMem`)
    — this stub has no node, so there is never a device to list."""

    def list_devices(self) -> list[DeviceInfo]:
        return []


class InprocTransport:
    """Implements `BridgeTransport` (verified structurally by the tests, not by explicit
    subclassing — `Protocol` is structural on purpose, see transport/base.py)."""

    def __init__(self) -> None:
        self._registry = _LoopbackRegistry()
        self._invocations = _LoopbackInvocations()
        self._started = False

    async def start(self) -> None:
        """Real at M0: this is what `HDPRuntime` calls on its owned loop, and the shape M1's
        aiohttp server lifecycle plugs into (server start/stop lives under `HDPRuntime`, not
        module import — docs/m0-plan.md §9)."""
        self._started = True

    async def close(self) -> None:
        self._started = False

    async def invoke(self, req: InvokeRequest) -> InvokeResult:
        # Bridge-side mint: at M0/M1 this stub *is* the bridge (FR-28, transport/base.py's
        # InvokeRequest docstring). The pending-table discipline is exercised even though
        # nothing here can actually time out or be cancelled yet.
        invocation_id, _entry = self._invocations.mint_for(
            req.device_id or "loopback", capability=req.capability
        )

        # Round-trip through the real codec so this stub exercises hdp_proto end to end, even
        # though the "wire" is a function call. A canned success is the honest answer here: there
        # is no node, so nothing produced this data except the stub itself (docs/m0-plan.md §M0-5).
        envelope = Envelope.new("invoke", {"capability": req.capability, "args": req.args})
        Envelope.from_wire(envelope.to_wire())  # exercise the round trip; discard the copy

        self._invocations.expire(invocation_id)  # remove before returning — FR-30's ordering rule
        return InvokeResult(invocation_id=invocation_id, ok=True, data={})

    async def cancel(self, invocation_id: str, reason: str) -> None:
        # Nothing calls this on the stub (nothing times out against a synchronous function call);
        # real cancellation lives in `socket.py`/`hdp_bridge` from M2 onward. Raising satisfies
        # docs/m0-plan.md §6.4's "returns not_implemented": `tools._handler` catches
        # NotImplementedError specifically and returns the ErrorCode.NOT_IMPLEMENTED shape, so the
        # code the model sees matches the taxonomy even though this signature can't return a
        # result of its own.
        raise NotImplementedError("cancel is not implemented until M1")

    async def list_devices(self) -> list[DeviceInfo]:
        return self._registry.list_devices()

    async def status(self) -> BridgeStatus:
        return BridgeStatus(healthy=self._started, detail="loopback stub (M0)")

    async def list_approvals(self) -> list[PendingApproval]:
        return []

    async def resolve_approval(self, invocation_id: str, decision: str, scope: str) -> None:
        # Unreachable until M3's approval flow exists. Same mechanism as `cancel` above:
        # `tools._handler` turns this raise into the ErrorCode.NOT_IMPLEMENTED result shape.
        raise NotImplementedError("resolve_approval is not implemented until M3")
