"""Security-order tests for the USB-only secondary enrollment entrypoint."""

from __future__ import annotations

import base64
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from hdp_bridge import operations
from hdp_bridge.enrollment import EnrollmentCoordinator
from hdp_bridge.host_identity import HostIdentityStore
from hdp_bridge.store import db
from hdp_bridge.usb_bootstrap import UsbBootstrapApproval, UsbBootstrapError, UsbBootstrapService


def _pubkey() -> str:
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    return base64.b64encode(
        key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode("ascii")


class _Owner:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls = 0

    async def authorize_pairing(self) -> bool:
        self.calls += 1
        return self.allowed


class _Peer:
    candidate_name = "Pixel"

    def __init__(self, pubkey: str, accepted: bool = True) -> None:
        self.device_pubkey = pubkey
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.device_pubkey = base64.b64encode(
            self.key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).decode("ascii")
        self.accepted = accepted
        self.delivered: tuple[str, str] | None = None
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def deliver_enrollment(self, request):
        self.delivered = (request.enrollment_id, request.host_public_key)
        if not self.accepted:
            return None
        host_fingerprint = (
            __import__("hashlib").sha256(base64.b64decode(request.host_public_key)).hexdigest()
        )
        payload = "\n".join((request.enrollment_id, host_fingerprint, self.device_pubkey)).encode()
        signature = self.key.sign(
            b"HDP/0 usb-candidate-approval\x00" + payload, ec.ECDSA(hashes.SHA256())
        )
        return UsbBootstrapApproval(
            request.enrollment_id,
            host_fingerprint,
            self.device_pubkey,
            base64.b64encode(signature).decode(),
        )


class _Primary:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    async def send_sentinel_approval_request(self, enrollment_id: str, candidate_name: str) -> None:
        self.requests.append((enrollment_id, candidate_name))


async def test_usb_bootstrap_requires_owner_auth_then_primary_notification(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    host = HostIdentityStore.load_or_create(tmp_path / "host.pem")
    owner = _Owner(True)
    peer = _Peer(_pubkey())
    primary = _Primary()
    service = UsbBootstrapService(
        EnrollmentCoordinator(conn),
        host_key_fingerprint=host.fingerprint,
        host_public_key=host.public_key,
        host_signer=host.sign,
        owner_authorizer=owner,
        primary_notifier=lambda: primary,
    )

    enrollment_id = await service.begin_secondary(peer)

    assert owner.calls == 1
    assert peer.delivered[0] == enrollment_id
    assert peer.closed
    assert primary.requests == [(enrollment_id, "Pixel")]
    state = conn.execute("SELECT state FROM pending_enrollments").fetchone()[0]
    assert state == "candidate_approved"


async def test_usb_bootstrap_fails_before_creating_state_without_owner_auth(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    host = HostIdentityStore.load_or_create(tmp_path / "host.pem")
    service = UsbBootstrapService(
        EnrollmentCoordinator(conn),
        host_key_fingerprint=host.fingerprint,
        host_public_key=host.public_key,
        host_signer=host.sign,
        owner_authorizer=_Owner(False),
        primary_notifier=lambda: _Primary(),
    )

    peer = _Peer(_pubkey())
    with pytest.raises(UsbBootstrapError, match="owner authorization"):
        await service.begin_secondary(peer)
    assert conn.execute("SELECT COUNT(*) FROM pending_enrollments").fetchone()[0] == 0
    assert peer.closed


async def test_usb_bootstrap_fails_closed_without_an_online_primary(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    host = HostIdentityStore.load_or_create(tmp_path / "host.pem")
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, state, first_paired_at, "
        "last_seen_at, role) "
        "VALUES ('primary', 'Primary', 'unknown', 'active', 0, 0, 'primary')"
    )
    service = UsbBootstrapService(
        EnrollmentCoordinator(conn),
        host_key_fingerprint=host.fingerprint,
        host_public_key=host.public_key,
        host_signer=host.sign,
        owner_authorizer=_Owner(True),
        primary_notifier=lambda: None,
    )

    peer = _Peer(_pubkey())
    with pytest.raises(UsbBootstrapError, match="primary device is offline"):
        await service.begin_secondary(peer)
    assert conn.execute("SELECT COUNT(*) FROM pending_enrollments").fetchone()[0] == 0
    assert peer.closed


async def test_preauthorized_bootstrap_does_not_repeat_owner_prompt(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    host = HostIdentityStore.load_or_create(tmp_path / "host.pem")
    owner = _Owner(True)
    peer = _Peer(_pubkey())
    service = UsbBootstrapService(
        EnrollmentCoordinator(conn),
        host_key_fingerprint=host.fingerprint,
        host_public_key=host.public_key,
        host_signer=host.sign,
        owner_authorizer=owner,
        primary_notifier=lambda: _Primary(),
    )

    await service.authorize_owner()
    await service.begin_secondary(peer, owner_authorized=True)

    assert owner.calls == 1
    assert peer.closed


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda approval: replace(approval, enrollment_id="other"), "current enrollment"),
        (
            lambda approval: replace(approval, host_fingerprint="other-host"),
            "different host identity",
        ),
        (
            lambda approval: replace(approval, device_public_key=_pubkey()),
            "different device identity",
        ),
    ],
)
async def test_usb_bootstrap_reports_which_candidate_binding_failed(tmp_path, mutator, message):
    conn = db.connect(tmp_path / "registry.db")
    host = HostIdentityStore.load_or_create(tmp_path / "host.pem")
    peer = _Peer(_pubkey())
    original_deliver = peer.deliver_enrollment

    async def deliver_bad(request):
        return mutator(await original_deliver(request))

    peer.deliver_enrollment = deliver_bad
    service = UsbBootstrapService(
        EnrollmentCoordinator(conn),
        host_key_fingerprint=host.fingerprint,
        host_public_key=host.public_key,
        host_signer=host.sign,
        owner_authorizer=_Owner(True),
        primary_notifier=lambda: _Primary(),
    )

    with pytest.raises(UsbBootstrapError, match=message):
        await service.begin_secondary(peer)
    assert peer.closed


async def test_pair_new_cannot_restore_the_retired_human_code_flow():
    with pytest.raises(operations.PairingCodeRemovedError, match="pairing codes are disabled"):
        await operations.pair_new()
