from __future__ import annotations

import pytest
from hdp_bridge.enrollment import (
    EnrollmentCoordinator,
    EnrollmentLockedError,
    EnrollmentNotReadyError,
    sentinel_approval_decision_bytes,
    sentinel_approval_request_bytes,
)
from hdp_bridge.store import db


def _add_primary(conn) -> None:
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, first_paired_at, last_seen_at, "
        "role) VALUES (?, ?, ?, ?, ?, ?)",
        ("primary-device", "sentinel", "android", 0, 0, "primary"),
    )
    conn.commit()


def test_enrollment_requires_candidate_and_primary_approval_before_consumption(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    _add_primary(conn)
    coordinator = EnrollmentCoordinator(conn)
    identifier = "a" * 64

    coordinator.start(
        identifier,
        host_key_fingerprint="host-fingerprint",
        candidate_key_fingerprint="candidate-fingerprint",
        now_ms=0,
    )
    coordinator.approve_candidate(identifier, now_ms=1)

    with pytest.raises(EnrollmentNotReadyError):
        coordinator.consume(
            identifier,
            host_key_fingerprint="host-fingerprint",
            candidate_key_fingerprint="candidate-fingerprint",
            now_ms=2,
        )
    coordinator.approve_primary(identifier, "primary-device", now_ms=3)

    assert (
        coordinator.consume(
            identifier,
            host_key_fingerprint="host-fingerprint",
            candidate_key_fingerprint="candidate-fingerprint",
            now_ms=4,
        )
        == "secondary"
    )


def test_first_usb_enrollment_becomes_primary_after_candidate_approval(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    coordinator = EnrollmentCoordinator(conn)
    identifier = "first" * 16

    coordinator.start(
        identifier,
        host_key_fingerprint="host-fingerprint",
        candidate_key_fingerprint="candidate-fingerprint",
        now_ms=0,
    )
    coordinator.approve_candidate(identifier, now_ms=1)

    assert (
        coordinator.consume(
            identifier,
            host_key_fingerprint="host-fingerprint",
            candidate_key_fingerprint="candidate-fingerprint",
            now_ms=2,
        )
        == "primary"
    )


def test_primary_block_cancels_the_request_and_locks_future_secondary_enrollment(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    _add_primary(conn)
    coordinator = EnrollmentCoordinator(conn)
    identifier = "b" * 64

    coordinator.start(
        identifier,
        host_key_fingerprint="host-fingerprint",
        candidate_key_fingerprint="candidate-fingerprint",
        now_ms=0,
    )
    coordinator.block(identifier, "primary-device", now_ms=1)

    with pytest.raises(EnrollmentNotReadyError):
        coordinator.consume(
            identifier,
            host_key_fingerprint="host-fingerprint",
            candidate_key_fingerprint="candidate-fingerprint",
            now_ms=2,
        )
    with pytest.raises(EnrollmentLockedError):
        coordinator.start(
            "c" * 64,
            host_key_fingerprint="host-fingerprint",
            candidate_key_fingerprint="another-candidate",
            now_ms=2,
        )


def test_sentinel_signature_payloads_are_domain_separated_and_canonical():
    assert sentinel_approval_request_bytes("id", "host", "candidate", "name", 42) == (
        b"HDP/0 sentinel-approval-request\x00id\nhost\ncandidate\nname\n42"
    )
    assert sentinel_approval_decision_bytes("id", "approve", 42) == (
        b"HDP/0 sentinel-approval-decision\x00id\napprove\n42"
    )
