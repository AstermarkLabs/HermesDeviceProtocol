"""In-memory approval lifecycle with terminal SQLite decision records."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_APPROVAL_TIMEOUT_S = 120.0


class ApprovalState(StrEnum):
    """Terminal approval outcomes persisted to the registry."""

    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalScope(StrEnum):
    """The permitted scope choices for an approval decision."""

    ONE_TIME = "one_time"
    SESSION = "session"
    DEVICE = "device"
    PERSISTENT = "persistent"


class UnknownApprovalError(KeyError):
    """Raised when an approval is no longer pending."""


@dataclass(frozen=True)
class PendingApproval:
    """The exact in-memory record for one invocation waiting on an operator."""

    invocation_id: str
    device_id: str
    capability: str
    version: int
    args_summary: str
    requesting_session: str | None
    risk_class: str
    created_at: float
    expires_at: float


@dataclass(frozen=True)
class ApprovalResolution:
    """One terminal decision and the approval it resolved."""

    state: ApprovalState
    pending: PendingApproval
    scope: ApprovalScope | None
    decided_by: str | None


class ApprovalManager:
    """Own live approvals; pending records never enter SQLite."""

    def __init__(
        self, conn: sqlite3.Connection, *, timeout_s: float = DEFAULT_APPROVAL_TIMEOUT_S
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._conn = conn
        self._timeout_s = timeout_s
        self._pending: dict[str, PendingApproval] = {}
        self._session_grants: set[tuple[str, str, str]] = set()
        self._waiters: dict[str, asyncio.Future[ApprovalResolution]] = {}

    def create(
        self,
        *,
        invocation_id: str,
        device_id: str,
        capability: str,
        version: int,
        args_summary: str,
        requesting_session: str | None,
        risk_class: str,
        now: float | None = None,
    ) -> PendingApproval:
        """Create a pending approval, rejecting duplicate invocation identifiers."""
        if invocation_id in self._pending:
            raise ValueError(f"approval {invocation_id!r} is already pending")
        created_at = time.monotonic() if now is None else now
        pending = PendingApproval(
            invocation_id=invocation_id,
            device_id=device_id,
            capability=capability,
            version=version,
            args_summary=args_summary,
            requesting_session=requesting_session,
            risk_class=risk_class,
            created_at=created_at,
            expires_at=created_at + self._timeout_s,
        )
        self._pending[invocation_id] = pending
        return pending

    def list_pending(self) -> list[PendingApproval]:
        """Return a stable presentation order without exposing internal state."""
        return sorted(self._pending.values(), key=lambda pending: pending.created_at)

    def resolve(
        self,
        invocation_id: str,
        *,
        approved: bool,
        scope: ApprovalScope | str = ApprovalScope.ONE_TIME,
        decided_by: str,
        now: float | None = None,
    ) -> ApprovalResolution:
        """Resolve one pending approval and persist exactly one terminal outcome."""
        pending = self._take_pending(invocation_id)
        resolved_scope = ApprovalScope(scope)
        if not approved:
            resolved_scope = None
        state = ApprovalState.APPROVED if approved else ApprovalState.DENIED
        resolution = ApprovalResolution(state, pending, resolved_scope, decided_by)
        self._record_terminal(resolution, now=now)
        if approved:
            self._grant(pending, resolved_scope, now=now)
        self._notify(resolution)
        return resolution

    def expire_pending(self, *, now: float | None = None) -> list[ApprovalResolution]:
        """Terminally expire every approval whose 120-second deadline has elapsed."""
        current = time.monotonic() if now is None else now
        expired: list[ApprovalResolution] = []
        for pending in list(self._pending.values()):
            if pending.expires_at > current:
                continue
            self._pending.pop(pending.invocation_id)
            resolution = ApprovalResolution(ApprovalState.EXPIRED, pending, None, None)
            self._record_terminal(resolution, now=current)
            self._notify(resolution)
            expired.append(resolution)
        return expired

    async def wait(self, invocation_id: str) -> ApprovalResolution:
        """Wait without holding a database transaction; expiry is a terminal decision."""
        pending = self._pending.get(invocation_id)
        if pending is None:
            raise UnknownApprovalError(invocation_id)
        waiter = self._waiters.get(invocation_id)
        if waiter is None:
            waiter = asyncio.get_running_loop().create_future()
            self._waiters[invocation_id] = waiter
        remaining = max(0.0, pending.expires_at - time.monotonic())
        try:
            return await asyncio.wait_for(asyncio.shield(waiter), timeout=remaining)
        except TimeoutError:
            self.expire_pending(now=pending.expires_at)
            return await waiter

    def has_session_grant(self, session_id: str | None, device_id: str, capability: str) -> bool:
        """Return whether a live daemon-local session grant covers the request."""
        return (
            session_id is not None and (session_id, device_id, capability) in self._session_grants
        )

    def has_database_grant(
        self, device_id: str, capability: str, *, now: float | None = None
    ) -> bool:
        """Return whether a non-revoked DEVICE or ALWAYS grant covers an ASK result."""
        current = time.time() if now is None else now
        row = self._conn.execute(
            """
            SELECT 1 FROM policy_grants
            WHERE device_id = ? AND capability = ? AND mode IN ('device', 'always')
              AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)
            LIMIT 1
            """,
            (device_id, capability, current),
        ).fetchone()
        return row is not None

    def _take_pending(self, invocation_id: str) -> PendingApproval:
        try:
            return self._pending.pop(invocation_id)
        except KeyError as exc:
            raise UnknownApprovalError(invocation_id) from exc

    def _record_terminal(self, resolution: ApprovalResolution, *, now: float | None) -> None:
        decided_at = int(time.time() if now is None else now)
        pending = resolution.pending
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO approvals (
                    invocation_id, device_id, capability, version, args_summary, requesting_session,
                    risk_class, state, decided_at, decided_by, scope
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pending.invocation_id,
                    pending.device_id,
                    pending.capability,
                    pending.version,
                    pending.args_summary,
                    pending.requesting_session,
                    pending.risk_class,
                    resolution.state.value,
                    decided_at,
                    resolution.decided_by,
                    resolution.scope.value if resolution.scope is not None else None,
                ),
            )

    def _grant(
        self, pending: PendingApproval, scope: ApprovalScope | None, *, now: float | None
    ) -> None:
        if scope is ApprovalScope.SESSION:
            if pending.requesting_session is not None:
                self._session_grants.add(
                    (pending.requesting_session, pending.device_id, pending.capability)
                )
            return
        if scope not in {ApprovalScope.DEVICE, ApprovalScope.PERSISTENT}:
            return
        mode = "device" if scope is ApprovalScope.DEVICE else "always"
        granted_at = int(time.time() if now is None else now)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO policy_grants (
                    device_id, capability, mode, scope, granted_at, expires_at,
                    session_id, revoked_at
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)
                """,
                (pending.device_id, pending.capability, mode, scope.value, granted_at),
            )

    def _notify(self, resolution: ApprovalResolution) -> None:
        waiter = self._waiters.pop(resolution.pending.invocation_id, None)
        if waiter is not None and not waiter.done():
            waiter.set_result(resolution)
