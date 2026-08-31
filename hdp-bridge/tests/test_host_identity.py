from __future__ import annotations

import stat

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from hdp_bridge.host_identity import HostIdentityStore


def test_host_identity_is_persistent_and_private_to_the_owner(tmp_path):
    path = tmp_path / "host-key.pem"

    first = HostIdentityStore.load_or_create(path)
    second = HostIdentityStore.load_or_create(path)

    assert first.fingerprint == second.fingerprint
    assert first.public_key == second.public_key
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_host_identity_signs_domain_separated_sentinel_payloads(tmp_path):
    identity = HostIdentityStore.load_or_create(tmp_path / "host-key.pem")
    payload = b"HDP/0 sentinel-approval-request\x00enrollment"

    signature = identity.sign(payload)

    identity.public_key_object.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
