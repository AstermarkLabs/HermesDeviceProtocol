"""Device public-key handling for HDP-0.md Amendments (v0.4).

The bridge verifies that a node holds the private half of the public key it presents, both when
pairing (before the key is bound to a new `device_id`) and on every reconnect thereafter. That
turns reconnect authentication into a two-secret path: the 256-bit credential proves *what* the
device knows, the signature proves the private key is *present on this device*. A credential file
lifted off a device is useless without the key, which on Android is non-exportable Keystore
material.

Crypto lives here, in the bridge, and not in `hdp_proto`: the codec is stdlib-only by design and
carries the key, nonce, and signature as opaque base64 strings without interpreting them.
"""

from __future__ import annotations

import base64
import binascii
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

#: Bytes of challenge nonce. 256 bits — far above any birthday concern across a bridge's lifetime,
#: and cheap enough that reuse is never worth attempting.
NONCE_BYTES = 32

#: Domain separation. A signature produced for a pairing challenge must not be replayable as a
#: reconnect proof, or a captured enrollment exchange would grant ongoing access.
PAIR_CONTEXT = b"HDP/0 pair-challenge\x00"
AUTH_CONTEXT = b"HDP/0 auth-challenge\x00"


class InvalidDeviceKeyError(ValueError):
    """The presented `device_pubkey` is not a usable EC P-256 public key."""


def new_nonce() -> str:
    """A fresh base64 challenge nonce."""
    return base64.b64encode(secrets.token_bytes(NONCE_BYTES)).decode("ascii")


def load_public_key(encoded: str) -> ec.EllipticCurvePublicKey:
    """Decode a base64 DER SubjectPublicKeyInfo and reject anything that is not EC P-256.

    Curve pinning is deliberate. Accepting whatever curve or algorithm a peer offers would let a
    node enroll with a key the bridge cannot meaningfully evaluate the strength of.
    """
    try:
        der = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidDeviceKeyError(f"device_pubkey is not valid base64: {exc}") from exc

    try:
        key = serialization.load_der_public_key(der)
    except Exception as exc:  # noqa: BLE001 — any decode failure is the same rejection
        raise InvalidDeviceKeyError(f"device_pubkey is not a valid DER public key: {exc}") from exc

    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise InvalidDeviceKeyError(f"device_pubkey is not an EC key: {type(key).__name__}")
    if not isinstance(key.curve, ec.SECP256R1):
        raise InvalidDeviceKeyError(f"device_pubkey uses unsupported curve {key.curve.name!r}")
    return key


def key_is_usable(encoded: str) -> bool:
    """Cheap pre-check so a structurally broken key is rejected before a challenge is issued
    rather than after a pointless round trip."""
    try:
        load_public_key(encoded)
    except InvalidDeviceKeyError:
        return False
    return True


def verify_proof(encoded_key: str, context: bytes, nonce: str, signature: str) -> bool:
    """Is `signature` a valid ECDSA-SHA256 signature over `context + nonce` by `encoded_key`?

    Returns False for every failure mode — bad key, bad base64, wrong signature — rather than
    distinguishing them to the caller. The caller's only correct response to any of them is the
    same `auth_failed`, and a more talkative return value would invite it to branch on why.
    """
    try:
        key = load_public_key(encoded_key)
    except InvalidDeviceKeyError:
        return False

    try:
        raw_signature = base64.b64decode(signature, validate=True)
        raw_nonce = base64.b64decode(nonce, validate=True)
    except (binascii.Error, ValueError):
        return False

    try:
        key.verify(raw_signature, context + raw_nonce, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False
    return True
