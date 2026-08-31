"""USB-only orchestration for a secondary-device enrollment.

The bridge deliberately knows no platform-specific USB API.  A small adapter (Android Open
Accessory on Linux, for example) proves that a device is physically attached and implements
``UsbBootstrapPeer``.  This service owns the security order: local owner authorization first,
then USB delivery of a high-entropy identifier, candidate confirmation, and finally a prompt to
the already-enrolled primary.  There is no network route to call this service.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from . import device_keys
from .enrollment import EnrollmentCoordinator


class OwnerAuthorizer(Protocol):
    """Platform adapter for a fresh OS/hardware-key authorization ceremony."""

    def authorize_pairing(self) -> Awaitable[bool]: ...


class UsbBootstrapPeer(Protocol):
    """A currently attached USB peer which can receive the opaque enrollment identifier."""

    candidate_name: str
    device_pubkey: str

    def deliver_enrollment(
        self, request: UsbBootstrapRequest
    ) -> Awaitable[UsbBootstrapApproval | None]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class UsbBootstrapRequest:
    enrollment_id: str
    host_public_key: str
    host_signature: str
    expires_at_ms: int
    endpoint: str
    tls_pin: str


@dataclass(frozen=True)
class UsbBootstrapApproval:
    enrollment_id: str
    host_fingerprint: str
    device_public_key: str
    candidate_signature: str


class PrimaryNotifier(Protocol):
    """The live connection of the one primary device."""

    def send_sentinel_approval_request(
        self, enrollment_id: str, candidate_name: str
    ) -> Awaitable[None]: ...


class UsbBootstrapError(RuntimeError):
    """The security preconditions for a USB bootstrap were not met."""


class UsbBootstrapService:
    """Start a code-free secondary enrollment after physical USB and local authorization."""

    def __init__(
        self,
        coordinator: EnrollmentCoordinator,
        *,
        host_key_fingerprint: str,
        host_public_key: str,
        host_signer: Callable[[bytes], bytes],
        owner_authorizer: OwnerAuthorizer,
        primary_notifier: Callable[[], PrimaryNotifier | None],
        endpoint: str = "wss://test.invalid/hdp/v0/socket",
        tls_pin: str = "sha256/test-pin",
    ) -> None:
        self._coordinator = coordinator
        self._host_key_fingerprint = host_key_fingerprint
        self._host_public_key = host_public_key
        self._host_signer = host_signer
        self._owner_authorizer = owner_authorizer
        self._primary_notifier = primary_notifier
        self._endpoint = endpoint
        self._tls_pin = tls_pin

    async def authorize_owner(self) -> None:
        """Require a fresh host-owner ceremony before touching a USB candidate."""
        if not await self._owner_authorizer.authorize_pairing():
            raise UsbBootstrapError("fresh local owner authorization was denied")

    async def begin_secondary(
        self, peer: UsbBootstrapPeer, *, owner_authorized: bool = False
    ) -> str:
        """Create and dispatch one enrollment after every local security gate succeeds."""
        try:
            if not owner_authorized:
                await self.authorize_owner()
            if not self._endpoint or not self._tls_pin:
                raise UsbBootstrapError(
                    "USB enrollment requires configured WSS endpoint and TLS certificate pin"
                )
            if not device_keys.key_is_usable(peer.device_pubkey):
                raise UsbBootstrapError("USB candidate presented an unusable device key")
            primary = self._primary_notifier()
            has_primary = self._coordinator.has_primary()
            if has_primary and primary is None:
                raise UsbBootstrapError(
                    "primary device is offline; secondary enrollment fails closed"
                )

            enrollment_id = secrets.token_urlsafe(32)
            self._coordinator.start(
                enrollment_id,
                host_key_fingerprint=self._host_key_fingerprint,
                candidate_key_fingerprint=device_keys.fingerprint(peer.device_pubkey),
            )
            _, _, expires_at = self._coordinator.details(enrollment_id)
            request_payload = _bootstrap_bytes(
                enrollment_id, self._host_public_key, expires_at, self._endpoint, self._tls_pin
            )
            request = UsbBootstrapRequest(
                enrollment_id=enrollment_id,
                host_public_key=self._host_public_key,
                host_signature=_b64(self._host_signer(request_payload)),
                expires_at_ms=expires_at,
                endpoint=self._endpoint,
                tls_pin=self._tls_pin,
            )
            approval = await peer.deliver_enrollment(request)
            if approval is None:
                raise UsbBootstrapError("USB candidate declined enrollment approval")
            self._require_valid_candidate_approval(peer, enrollment_id, approval)
            self._coordinator.approve_candidate(enrollment_id)
            if primary is not None:
                await primary.send_sentinel_approval_request(enrollment_id, peer.candidate_name)
        except BaseException:
            # A delivery failure must not leave a live credential-like enrollment identifier.
            if "enrollment_id" in locals():
                self._coordinator.cancel(enrollment_id)
            raise
        finally:
            # Never retain a libusb claim after cancellation or a rejected security gate.
            peer.close()
        return enrollment_id

    def _require_valid_candidate_approval(
        self, peer: UsbBootstrapPeer, enrollment_id: str, approval: UsbBootstrapApproval
    ) -> None:
        if approval.enrollment_id != enrollment_id:
            raise UsbBootstrapError("USB candidate approval did not bind the current enrollment")
        if approval.host_fingerprint != self._host_key_fingerprint:
            raise UsbBootstrapError("USB candidate approval named a different host identity")
        if approval.device_public_key != peer.device_pubkey:
            raise UsbBootstrapError("USB candidate approval named a different device identity")
        payload = _candidate_bytes(
            approval.enrollment_id, approval.host_fingerprint, approval.device_public_key
        )
        if not device_keys.verify_signature(
            approval.device_public_key,
            b"HDP/0 usb-candidate-approval\x00" + payload,
            approval.candidate_signature,
        ):
            raise UsbBootstrapError("USB candidate approval signature did not verify")


def _bootstrap_bytes(
    enrollment_id: str,
    host_public_key: str,
    expires_at_ms: int,
    endpoint: str = "",
    tls_pin: str = "",
) -> bytes:
    return b"HDP/0 usb-bootstrap\x00" + "\n".join(
        (enrollment_id, host_public_key, str(expires_at_ms), endpoint, tls_pin)
    ).encode("utf-8")


def _candidate_bytes(enrollment_id: str, host_fingerprint: str, device_public_key: str) -> bytes:
    return "\n".join((enrollment_id, host_fingerprint, device_public_key)).encode("utf-8")


def _b64(value: bytes) -> str:
    import base64

    return base64.b64encode(value).decode("ascii")
