"""The bridge-side pending-invocation table — id → in-flight marker.

Named to match the eventual `hdp_bridge/invocations.py` at M2 (design §3, ADR-0004). At M0 the
loopback stub resolves every invocation synchronously, so nothing here ever actually blocks or
times out — but the discipline is already in place: an id is registered before the "call" and
removed **before** any cancel/timeout handling runs (FR-30), so the shape M1 needs (a real
pending table backing real timeouts and cancellation over a real socket) drops in without
restructuring this module's contract.
"""

from __future__ import annotations

from hdp_proto import ids


class InvocationsMem:
    """Tracks which invocation ids are currently in flight. Empty by construction outside the
    (synchronous, instantaneous) window of a single `invoke()` call at M0."""

    def __init__(self) -> None:
        self._pending: set[str] = set()

    def mint(self) -> str:
        """Mint a fresh, bridge-side invocation id (FR-28) and register it as pending."""
        invocation_id = ids.new()
        self._pending.add(invocation_id)
        return invocation_id

    def drop(self, invocation_id: str) -> None:
        """Remove an id from the pending table. Idempotent — dropping an unknown/already-dropped
        id is a silent no-op, matching the "late result" handling M1 formalizes (FR-30)."""
        self._pending.discard(invocation_id)

    def is_pending(self, invocation_id: str) -> bool:
        return invocation_id in self._pending

    def __len__(self) -> int:
        return len(self._pending)
