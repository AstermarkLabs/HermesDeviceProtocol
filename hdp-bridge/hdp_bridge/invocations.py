"""The bridge-side pending-invocation table — id → in-flight state.

Backs real ack-timeout / execution-deadline / cancel / mid-call-disconnect handling over a real
socket (hdp-spec/HDP-0.md §7). Two `asyncio.Future`s per entry, not one, because "acked" and
"resolved" are genuinely separate events with separate timeouts (ack timeout 5s, strictly less
than the execution deadline) — collapsing them into one future would make it impossible to tell
"never acked" from "acked but never resolved" apart, and those two cases return different error
codes (`device_offline` vs `invocation_timeout`).

FR-30's ordering rule — remove the pending entry *before* sending a best-effort `cancel` — lives
here as `expire()`, so the one call the timeout paths in `embedded.py` make cannot be reordered
by accident at the call site.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from hdp_proto import ids


class DeviceDisconnected(Exception):
    """Set as the exception on whichever future (ack or result) is still pending when a device's
    connection drops mid-invocation — this is what makes `fail_all_for_device` interrupt an
    in-progress `asyncio.wait_for` immediately rather than waiting out its timeout (HDP-0.md §7's
    "mid-call disconnect fails in-flight invocations immediately" rule)."""


@dataclass
class PendingInvocation:
    device_id: str
    ack_future: asyncio.Future[None]
    result_future: asyncio.Future[dict[str, Any]]
    capability: str = ""


@dataclass
class InvocationsMem:
    """Tracks in-flight invocations. Empty by construction; entries live only between `mint_for`
    and whichever of `resolve`/`expire`/`fail_all_for_device` removes them."""

    _pending: dict[str, PendingInvocation] = field(default_factory=dict)

    def mint_for(self, device_id: str, *, capability: str = "") -> tuple[str, PendingInvocation]:
        """Mint a fresh, bridge-side invocation id (FR-28) and register it as pending."""
        loop = asyncio.get_running_loop()
        invocation_id = ids.new()
        entry = PendingInvocation(
            device_id=device_id,
            ack_future=loop.create_future(),
            result_future=loop.create_future(),
            capability=capability,
        )
        self._pending[invocation_id] = entry
        return invocation_id, entry

    def mark_acked(self, invocation_id: str) -> bool:
        """Called when an `ack` frame arrives. Returns `False` (a silent no-op) for an unknown or
        already-terminal id — a late ack is not an error, just information nobody needs anymore."""
        entry = self._pending.get(invocation_id)
        if entry is None or entry.ack_future.done():
            return False
        entry.ack_future.set_result(None)
        return True

    def resolve(self, invocation_id: str, result: dict[str, Any]) -> bool:
        """Called when a `result` frame arrives. Returns `False` for an unknown id — the
        late-result path (HDP-0.md §7): dropped silently here, logged by the caller."""
        entry = self._pending.pop(invocation_id, None)
        if entry is None:
            return False
        # Deliberately does NOT also resolve `ack_future` here: HDP-0.md §7's ack-timeout rule is
        # strict ("a node that never acks fails early"), so a result arriving without a prior
        # explicit `ack` must not retroactively count as one — that would let a node skip acking
        # and still succeed, defeating the whole point of `device_offline` on ack timeout. In the
        # normal case `ack_future` is already done by the time a real `result` arrives, because
        # `NodeConnection` processes frames in the order the node sent them.
        if not entry.result_future.done():
            entry.result_future.set_result(result)
        return True

    def expire(self, invocation_id: str) -> PendingInvocation | None:
        """Atomically remove and return the entry (or `None` if already gone) without touching
        either future — used by the ack-timeout and execution-deadline paths in `embedded.py`,
        which already know the outcome from their own `asyncio.wait_for` timing out and only need
        the entry removed *before* they send a best-effort `cancel` (FR-30's ordering rule)."""
        return self._pending.pop(invocation_id, None)

    def fail_all(self) -> list[str]:
        """Fail every pending invocation regardless of device — used on transport shutdown
        (`EmbeddedTransport.close()`), as a defensive backstop; the normal per-connection
        disconnect path is `fail_all_for_device`, not this."""
        return self._fail(device_id=None)

    def fail_all_for_device(self, device_id: str) -> list[str]:
        """A device's connection dropped: fail every invocation still pending for it, immediately,
        by raising `DeviceDisconnected` on whichever future (ack or result) is still outstanding.
        Returns the list of invocation ids that were failed, for logging."""
        return self._fail(device_id=device_id)

    def _fail(self, *, device_id: str | None) -> list[str]:
        """Remove and fail every pending entry (all of them when `device_id` is `None`). The
        exception goes on exactly one future — `elif`, not a second `if`: setting it on both would
        leave the ack future's exception unretrieved once the awaiter has already bailed out on
        the first one, which surfaces as asyncio's "exception was never retrieved" noise."""
        failed: list[str] = []
        for invocation_id, entry in list(self._pending.items()):
            if device_id is not None and entry.device_id != device_id:
                continue
            del self._pending[invocation_id]
            if not entry.ack_future.done():
                entry.ack_future.set_exception(DeviceDisconnected())
            elif not entry.result_future.done():
                entry.result_future.set_exception(DeviceDisconnected())
            failed.append(invocation_id)
        return failed

    def is_pending(self, invocation_id: str) -> bool:
        return invocation_id in self._pending

    def __len__(self) -> int:
        return len(self._pending)
