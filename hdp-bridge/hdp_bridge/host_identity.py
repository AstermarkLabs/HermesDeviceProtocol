"""Persistent signing identity for one Hermes/HDP host."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


@dataclass(frozen=True)
class HostIdentityStore:
    """A host's P-256 key, its wire-format public key, and stable fingerprint."""

    _private_key: ec.EllipticCurvePrivateKey
    public_key: str
    fingerprint: str

    @classmethod
    def load_or_create(cls, path: Path) -> HostIdentityStore:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            private_key = _load_private_key(path)
        except FileNotFoundError:
            private_key = ec.generate_private_key(ec.SECP256R1())
            try:
                _write_private_key(path, private_key)
            except FileExistsError:
                private_key = _load_private_key(path)
        public_der = private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return cls(
            _private_key=private_key,
            public_key=base64.b64encode(public_der).decode("ascii"),
            fingerprint=hashlib.sha256(public_der).hexdigest(),
        )

    @property
    def public_key_object(self) -> ec.EllipticCurvePublicKey:
        return self._private_key.public_key()

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload, ec.ECDSA(hashes.SHA256()))


def _load_private_key(path: Path) -> ec.EllipticCurvePrivateKey:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        os.fchmod(fd, 0o600)
        key = serialization.load_pem_private_key(handle.read(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("host identity must be an EC P-256 private key")
    return key


def _write_private_key(path: Path, private_key: ec.EllipticCurvePrivateKey) -> None:
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        os.fchmod(fd, 0o600)
        handle.write(pem)
