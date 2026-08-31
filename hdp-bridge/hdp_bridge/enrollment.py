"""Durable, fail-closed state transitions for USB-sentinel device enrollment."""

from __future__ import annotations

import hashlib
import sqlite3
import time


class EnrollmentError(RuntimeError):
    """Base error for a pending device enrollment."""


class EnrollmentNotReadyError(EnrollmentError):
    """The candidate and primary approvals have not both been recorded."""


class EnrollmentNotFoundError(EnrollmentError):
    """No pending enrollment matches the presented opaque identifier."""


class EnrollmentLockedError(EnrollmentError):
    """A primary device blocked new secondary enrollment for this profile."""


class EnrollmentAlreadyPendingError(EnrollmentError):
    """A profile may have only one live secondary enrollment at a time."""


class EnrollmentCoordinator:
    """Own the one-pending, two-approval enrollment state machine.

    The caller receives an opaque identifier from the USB bootstrap. Only its SHA-256 digest is
    stored. Both approval timestamps and both key fingerprints are checked by the one consuming
    update, which prevents a replay from consuming an enrollment for another host or device.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def has_primary(self) -> bool:
        return (
            self._conn.execute("SELECT 1 FROM devices WHERE role = 'primary'").fetchone()
            is not None
        )

    def start(
        self,
        identifier: str,
        *,
        host_key_fingerprint: str,
        candidate_key_fingerprint: str,
        now_ms: int | None = None,
    ) -> None:
        now_ms = _now_ms(now_ms)
        identifier_hash = _identifier_hash(identifier)
        with self._conn:
            if self._conn.execute("SELECT 1 FROM pairing_locks WHERE profile_lock = 1").fetchone():
                raise EnrollmentLockedError("secondary enrollment is locked by the primary device")
            self._expire_live_enrollments(now_ms)
            if self._conn.execute(
                "SELECT 1 FROM pending_enrollments WHERE state IN "
                "('pending', 'candidate_approved', 'primary_approved')"
            ).fetchone():
                raise EnrollmentAlreadyPendingError("a secondary enrollment is already pending")
            has_primary = self._conn.execute(
                "SELECT 1 FROM devices WHERE role = 'primary'"
            ).fetchone()
            target_role = "secondary" if has_primary else "primary"
            # A profile with no sentinel is recovered by the same fresh local owner ceremony
            # that calls start(). Candidate confirmation remains mandatory; no network peer can
            # manufacture this transition because only the USB bootstrap service exposes start.
            primary_approved_at = None if has_primary else now_ms
            state = "pending" if has_primary else "primary_approved"
            self._conn.execute(
                "INSERT INTO pending_enrollments (identifier_hash, host_key_fingerprint, "
                "candidate_key_fingerprint, state, created_at, expires_at, "
                "primary_approved_at, target_role) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    identifier_hash,
                    host_key_fingerprint,
                    candidate_key_fingerprint,
                    state,
                    now_ms,
                    now_ms + 2 * 60 * 1000,
                    primary_approved_at,
                    target_role,
                ),
            )

    def approve_candidate(self, identifier: str, *, now_ms: int | None = None) -> None:
        now_ms = _now_ms(now_ms)
        self._approve(identifier, column="candidate_approved_at", now_ms=now_ms)

    def approve_primary(
        self, identifier: str, primary_device_id: str, *, now_ms: int | None = None
    ) -> None:
        now_ms = _now_ms(now_ms)
        self._require_current_primary(primary_device_id)
        self._approve(
            identifier,
            column="primary_approved_at",
            primary_device_id=primary_device_id,
            now_ms=now_ms,
        )

    def block(self, identifier: str, primary_device_id: str, *, now_ms: int | None = None) -> None:
        """Cancel one live request and contain subsequent secondary enrollment attempts."""
        now_ms = _now_ms(now_ms)
        self._require_current_primary(primary_device_id)
        identifier_hash = _identifier_hash(identifier)
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE pending_enrollments SET state = 'blocked' WHERE identifier_hash = ? "
                "AND expires_at > ? AND state IN "
                "('pending', 'candidate_approved', 'primary_approved')",
                (identifier_hash, now_ms),
            )
            if cursor.rowcount != 1:
                row = self._conn.execute(
                    "SELECT 1 FROM pending_enrollments WHERE identifier_hash = ?",
                    (identifier_hash,),
                ).fetchone()
                if row is None:
                    raise EnrollmentNotFoundError("unknown enrollment identifier")
                raise EnrollmentNotReadyError("enrollment is expired or already terminal")
            self._conn.execute(
                "INSERT INTO pairing_locks (profile_lock, locked_at, blocked_by_device_id) "
                "VALUES (1, ?, ?) ON CONFLICT(profile_lock) DO UPDATE SET "
                "locked_at = excluded.locked_at, "
                "blocked_by_device_id = excluded.blocked_by_device_id",
                (now_ms, primary_device_id),
            )

    def deny(self, identifier: str, primary_device_id: str, *, now_ms: int | None = None) -> None:
        """Cancel one live request without locking future enrollment."""
        now_ms = _now_ms(now_ms)
        self._require_current_primary(primary_device_id)
        self._set_terminal_state(identifier, "denied", now_ms)

    def cancel(self, identifier: str, *, now_ms: int | None = None) -> None:
        """Abort a just-created request after local USB delivery fails or is declined."""
        self._set_terminal_state(identifier, "denied", _now_ms(now_ms))

    def details(self, identifier: str, *, now_ms: int | None = None) -> tuple[str, str, int]:
        """Return immutable bindings needed to verify or prompt for a live enrollment."""
        now_ms = _now_ms(now_ms)
        row = self._conn.execute(
            "SELECT host_key_fingerprint, candidate_key_fingerprint, expires_at "
            "FROM pending_enrollments WHERE identifier_hash = ? AND expires_at > ? "
            "AND state IN ('pending', 'candidate_approved', 'primary_approved')",
            (_identifier_hash(identifier), now_ms),
        ).fetchone()
        if row is None:
            raise EnrollmentNotFoundError("unknown, expired, or terminal enrollment identifier")
        return (str(row[0]), str(row[1]), int(row[2]))

    def consume(
        self,
        identifier: str,
        *,
        host_key_fingerprint: str,
        candidate_key_fingerprint: str,
        now_ms: int | None = None,
    ) -> str:
        now_ms = _now_ms(now_ms)
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE pending_enrollments SET state = 'consumed', consumed_at = ? "
                "WHERE identifier_hash = ? AND host_key_fingerprint = ? "
                "AND candidate_key_fingerprint = ? AND candidate_approved_at IS NOT NULL "
                "AND primary_approved_at IS NOT NULL AND expires_at > ? "
                "AND state IN ('candidate_approved', 'primary_approved')",
                (
                    now_ms,
                    _identifier_hash(identifier),
                    host_key_fingerprint,
                    candidate_key_fingerprint,
                    now_ms,
                ),
            )
            if cursor.rowcount == 1:
                return str(
                    self._conn.execute(
                        "SELECT target_role FROM pending_enrollments WHERE identifier_hash = ?",
                        (_identifier_hash(identifier),),
                    ).fetchone()[0]
                )
            row = self._conn.execute(
                "SELECT state, expires_at FROM pending_enrollments WHERE identifier_hash = ?",
                (_identifier_hash(identifier),),
            ).fetchone()
            if row is None:
                raise EnrollmentNotFoundError("unknown enrollment identifier")
            if row[1] <= now_ms and row[0] in {
                "pending",
                "candidate_approved",
                "primary_approved",
            }:
                self._conn.execute(
                    "UPDATE pending_enrollments SET state = 'expired' WHERE identifier_hash = ?",
                    (_identifier_hash(identifier),),
                )
            raise EnrollmentNotReadyError("enrollment lacks required approvals or key binding")

    def _approve(
        self,
        identifier: str,
        *,
        column: str,
        now_ms: int,
        primary_device_id: str | None = None,
    ) -> None:
        identifier_hash = _identifier_hash(identifier)
        if column == "candidate_approved_at":
            query = (
                "UPDATE pending_enrollments SET candidate_approved_at = ?, state = "
                "'candidate_approved' WHERE identifier_hash = ? AND expires_at > ? "
                "AND state IN ('pending', 'candidate_approved', 'primary_approved')"
            )
            params: tuple[object, ...] = (now_ms, identifier_hash, now_ms)
        elif column == "primary_approved_at" and primary_device_id is not None:
            query = (
                "UPDATE pending_enrollments SET primary_approved_at = ?, primary_device_id = ?, "
                "state = 'primary_approved' WHERE identifier_hash = ? AND expires_at > ? "
                "AND state IN ('pending', 'candidate_approved', 'primary_approved')"
            )
            params = (now_ms, primary_device_id, identifier_hash, now_ms)
        else:  # pragma: no cover - private callers provide one of the two approved variants.
            raise ValueError("unsupported enrollment approval")
        with self._conn:
            cursor = self._conn.execute(query, params)
            if cursor.rowcount == 1:
                return
            row = self._conn.execute(
                "SELECT 1 FROM pending_enrollments WHERE identifier_hash = ?",
                (_identifier_hash(identifier),),
            ).fetchone()
            if row is None:
                raise EnrollmentNotFoundError("unknown enrollment identifier")
            raise EnrollmentNotReadyError("enrollment is expired or already terminal")

    def _set_terminal_state(self, identifier: str, state: str, now_ms: int) -> None:
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE pending_enrollments SET state = ? WHERE identifier_hash = ? "
                "AND expires_at > ? AND state IN "
                "('pending', 'candidate_approved', 'primary_approved')",
                (state, _identifier_hash(identifier), now_ms),
            )
            if cursor.rowcount == 1:
                return
            row = self._conn.execute(
                "SELECT 1 FROM pending_enrollments WHERE identifier_hash = ?",
                (_identifier_hash(identifier),),
            ).fetchone()
            if row is None:
                raise EnrollmentNotFoundError("unknown enrollment identifier")
            raise EnrollmentNotReadyError("enrollment is expired or already terminal")

    def _expire_live_enrollments(self, now_ms: int) -> None:
        self._conn.execute(
            "UPDATE pending_enrollments SET state = 'expired' WHERE expires_at <= ? "
            "AND state IN ('pending', 'candidate_approved', 'primary_approved')",
            (now_ms,),
        )

    def _require_current_primary(self, device_id: str) -> None:
        primary = self._conn.execute(
            "SELECT 1 FROM devices WHERE device_id = ? AND role = 'primary'", (device_id,)
        ).fetchone()
        if primary is None:
            raise EnrollmentNotReadyError("approval must come from the current primary device")


def _identifier_hash(identifier: str) -> str:
    if not identifier:
        raise ValueError("enrollment identifier must not be empty")
    return hashlib.sha256(identifier.encode("ascii")).hexdigest()


def _now_ms(now_ms: int | None) -> int:
    return now_ms if now_ms is not None else int(time.time() * 1000)


def sentinel_approval_request_bytes(
    enrollment_id: str,
    host_key_fingerprint: str,
    candidate_key_fingerprint: str,
    candidate_name: str,
    expires_at: int,
) -> bytes:
    """Canonical, host-signed bytes for a primary-device approval prompt."""
    fields = (
        enrollment_id,
        host_key_fingerprint,
        candidate_key_fingerprint,
        candidate_name,
        str(expires_at),
    )
    return b"HDP/0 sentinel-approval-request\x00" + "\n".join(fields).encode("utf-8")


def sentinel_approval_decision_bytes(enrollment_id: str, decision: str, expires_at: int) -> bytes:
    """Canonical, primary-device-signed bytes for one sentinel decision."""
    return b"HDP/0 sentinel-approval-decision\x00" + "\n".join(
        (enrollment_id, decision, str(expires_at))
    ).encode("utf-8")
