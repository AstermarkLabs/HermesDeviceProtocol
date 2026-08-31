"""Pinned, self-signed TLS identity for direct HDP node connections."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def load_or_create(cert_path: Path, key_path: Path, endpoint: str) -> tuple[ssl.SSLContext, str]:
    """Return the server context and SPKI pin bound into a USB bootstrap."""
    if not cert_path.exists() or not key_path.exists():
        _write_identity(cert_path, key_path, urlparse(endpoint).hostname or "")
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    spki = certificate.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pin = "sha256/" + base64.b64encode(hashlib.sha256(spki).digest()).decode("ascii")
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(cert_path, key_path)
    return context, pin


def _write_identity(cert_path: Path, key_path: Path, host: str) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    try:
        san = x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        san = x509.DNSName(host)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([san]), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
