"""The M0/M1 loopback `BridgeTransport`: no server, no socket, no node.

This isolates the loop-ownership question (M0's actual risk, ADR-0002) from the protocol
question. `invoke()` round-trips a real `hdp_proto.Envelope` — so the codec is exercised even
though nothing serializes it to bytes — and returns a canned success, because M0 has no node to
produce a real one. `docs/m0-plan.md` §6.4 and §M0-5 name this precisely: a red M0 test means
"the loop pattern doesn't hold," never "the wire is wrong," because there is no wire yet.

Retained after M1 as a fast, dependency-free test transport (design §2's module docstring) —
this class does not go away when `socket.py` ships.
"""

from __future__ import annotations

from hdp_proto.envelope import Envelope

from ._invocations import InvocationsMem
from ._registry_mem import RegistryMem
from .base import (
    BridgeStatus,
    DeviceInfo,
    InvokeRequest,
    InvokeResult,
    PendingApproval,
)


class InprocTransport:
    """Implements `BridgeTransport` (verified structurally by the tests, not by explicit
    subclassing — `Protocol` is structural on purpose, see transport/base.py)."""

    def __init__(self) -> None:
        self._registry = RegistryMem()
        self._invocations = InvocationsMem()
        self._started = False

    async def start(self) -> None:
        """Real at M0: this is what `HDPRuntime` calls on its owned loop, and the shape M1's
        aiohttp server lifecycle plugs into (server start/stop lives under `HDPRuntime`, not
        module import — docs/m0-plan.md §9)."""
        self._started = True

    async def close(self) -> None:
        self._started = False

    async def invoke(self, req: InvokeRequest) -> InvokeResult:
        # Bridge-side mint: at M0 this stub *is* the bridge (FR-28, transport/base.py's
        # InvokeRequest docstring). The pending-table discipline is exercised even though
        # nothing here can actually time out or be cancelled yet.
        invocation_id = self._invocations.mint()

        # Round-trip through the real codec so M0 exercises hdp_proto end to end, even though
        # the "wire" is a function call. A canned success is the honest answer here: there is no
        # node, so nothing produced this data except the stub itself (docs/m0-plan.md §M0-5).
        envelope = Envelope.new("invoke", {"capability": req.capability, "args": req.args})
        Envelope.from_wire(envelope.to_wire())  # exercise the round trip; discard the copy

        self._invocations.drop(invocation_id)  # drop before returning — FR-30's ordering rule
        return InvokeResult(invocation_id=invocation_id, ok=True, data={})

    async def cancel(self, invocation_id: str, reason: str) -> None:
        # Nothing at M0 calls this (ASK is unreachable, nothing times out against a synchronous
        # stub). docs/m0-plan.md §6.4 says this "returns not_implemented" — but `_handler` maps
        # a raised NotImplementedError to BRIDGE_UNAVAILABLE, not ErrorCode.NOT_IMPLEMENTED. M1,
        # when it wires real cancellation, should return the ErrorCode.NOT_IMPLEMENTED result
        # shape rather than raise, so the code the model sees matches the taxonomy.
        raise NotImplementedError("cancel is not implemented until M1")

    async def list_devices(self) -> list[DeviceInfo]:
        return self._registry.list_devices()

    async def status(self) -> BridgeStatus:
        return BridgeStatus(healthy=self._started, detail="loopback stub (M0)")

    async def list_approvals(self) -> list[PendingApproval]:
        return []

    async def resolve_approval(self, invocation_id: str, decision: str, scope: str) -> None:
        # Same discrepancy as `cancel` above: docs/m0-plan.md §6.4 says "returns
        # not_implemented", but raising here surfaces as BRIDGE_UNAVAILABLE through `_handler`,
        # not ErrorCode.NOT_IMPLEMENTED. Unreachable until M3's approval flow exists; M3 should
        # return the NOT_IMPLEMENTED result shape rather than raise.
        raise NotImplementedError("resolve_approval is not implemented until M3")
