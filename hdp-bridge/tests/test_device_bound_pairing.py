"""HDP-0.md Amendments (v0.4): challenge-response enrollment and device-bound reconnect.

Drives `NodeConnection` directly through the same `_FakeWS` double the M2 auth tests use, so the
handshake state machine is exercised without standing up a real aiohttp server.
"""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from hdp_bridge import credentials, device_keys, pairing
from hdp_bridge.connection import NodeConnection
from hdp_bridge.invocations import InvocationsMem
from hdp_bridge.registry import Registry
from hdp_bridge.store import db
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Challenge, Hello, Proof, Welcome


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_str(self, data):
        self.sent.append(data)

    async def close(self, *, code, message=b""):
        self.closed_with = code

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def _new_key():
    private = ec.generate_private_key(ec.SECP256R1())
    encoded = base64.b64encode(
        private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode("ascii")
    return private, encoded


def _sign(private, context: bytes, nonce: str) -> str:
    signature = private.sign(context + base64.b64decode(nonce), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("ascii")


def _connection(tmp_path, conn=None):
    db_path = tmp_path / "registry.db"
    conn = conn or db.connect(db_path)
    ws = _FakeWS()
    return (
        ws,
        conn,
        NodeConnection(
            ws,
            conn=conn,
            registry=Registry(db_path),
            invocations=InvocationsMem(),
            connections={},
            descriptors={},
        ),
    )


async def _send(connection, type_: str, payload: dict) -> None:
    await connection._handle_frame(json.dumps(Envelope.new(type_, payload).to_wire()))


def _last(ws) -> Envelope:
    return Envelope.from_wire(json.loads(ws.sent[-1]))


async def _enroll(tmp_path, conn=None):
    """Complete a full v0.4 enrollment; returns (private key, device_id, credential, conn)."""
    ws, conn, connection = _connection(tmp_path, conn)
    code = pairing.mint_pairing_code(conn)
    private, pubkey = _new_key()

    hello = Hello(
        hdp_versions=(0,),
        device_name="pixel",
        capabilities=(),
        credential=f"pair:{code}",
        platform="android",
        device_pubkey=pubkey,
    )
    await _send(connection, "hello", hello.to_wire())

    challenge = Challenge.from_wire(_last(ws).payload)
    await _send(
        connection,
        "proof",
        Proof(signature=_sign(private, device_keys.PAIR_CONTEXT, challenge.nonce)).to_wire(),
    )
    welcome = Welcome.from_wire(_last(ws).payload)
    return private, welcome.device_id, welcome.credential, conn


async def test_pairing_challenges_before_issuing_anything(tmp_path):
    ws, conn, connection = _connection(tmp_path)
    code = pairing.mint_pairing_code(conn)
    _, pubkey = _new_key()

    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,),
            device_name="pixel",
            capabilities=(),
            credential=f"pair:{code}",
            device_pubkey=pubkey,
        ).to_wire(),
    )

    assert _last(ws).type == "challenge"
    # No identity, no credential, and crucially the code is still live: nothing is committed
    # until possession of the private key has been proven.
    assert connection.device_id is None
    assert pairing.code_is_live(conn, code) is True


async def test_valid_proof_completes_pairing_and_binds_the_key(tmp_path):
    private, device_id, credential, conn = await _enroll(tmp_path)
    assert device_id is not None
    assert credential is not None
    stored = conn.execute(
        "SELECT device_pubkey FROM devices WHERE device_id = ?", (device_id,)
    ).fetchone()[0]
    assert stored != ""


async def test_wrong_key_fails_pairing_and_burns_the_code(tmp_path):
    """A guesser who lands the right code but holds no matching key gets nothing, and pays for
    the attempt out of the code's budget."""
    ws, conn, connection = _connection(tmp_path)
    code = pairing.mint_pairing_code(conn)
    _, pubkey = _new_key()
    attacker, _ = _new_key()  # different key than the one enrolled

    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,),
            device_name="pixel",
            capabilities=(),
            credential=f"pair:{code}",
            device_pubkey=pubkey,
        ).to_wire(),
    )
    challenge = Challenge.from_wire(_last(ws).payload)
    await _send(
        connection,
        "proof",
        Proof(signature=_sign(attacker, device_keys.PAIR_CONTEXT, challenge.nonce)).to_wire(),
    )

    assert ws.closed_with is not None
    assert connection.device_id is None
    remaining = conn.execute("SELECT attempts_remaining FROM pairing_codes").fetchone()[0]
    assert remaining == 4


async def test_a_pairing_signature_cannot_be_replayed_as_a_reconnect_proof(tmp_path):
    """Domain separation. Without distinct contexts a captured enrollment exchange would grant
    ongoing access, which is the whole point of signing the reconnect separately."""
    private, device_id, credential, conn = await _enroll(tmp_path)

    ws, conn, connection = _connection(tmp_path, conn)
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,), device_name="pixel", capabilities=(), credential=credential
        ).to_wire(),
    )
    challenge = Challenge.from_wire(_last(ws).payload)
    # Signed with the *pairing* context rather than the auth context.
    await _send(
        connection,
        "proof",
        Proof(signature=_sign(private, device_keys.PAIR_CONTEXT, challenge.nonce)).to_wire(),
    )

    assert ws.closed_with is not None
    assert connection.device_id is None


async def test_reconnect_requires_both_the_credential_and_the_key(tmp_path):
    private, device_id, credential, conn = await _enroll(tmp_path)

    ws, conn, connection = _connection(tmp_path, conn)
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,), device_name="pixel", capabilities=(), credential=credential
        ).to_wire(),
    )
    # A correct credential alone gets a challenge, not a welcome.
    assert _last(ws).type == "challenge"
    challenge = Challenge.from_wire(_last(ws).payload)

    await _send(
        connection,
        "proof",
        Proof(signature=_sign(private, device_keys.AUTH_CONTEXT, challenge.nonce)).to_wire(),
    )
    assert _last(ws).type == "welcome"
    assert Welcome.from_wire(_last(ws).payload).device_id == device_id
    assert connection.device_id == device_id


async def test_a_stolen_credential_is_useless_without_the_device_key(tmp_path):
    """The headline v0.4 claim: lifting the credential file off a device buys nothing, because
    the private half never leaves the device's keystore."""
    _, device_id, credential, conn = await _enroll(tmp_path)
    thief, _ = _new_key()

    ws, conn, connection = _connection(tmp_path, conn)
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,), device_name="attacker", capabilities=(), credential=credential
        ).to_wire(),
    )
    challenge = Challenge.from_wire(_last(ws).payload)
    await _send(
        connection,
        "proof",
        Proof(signature=_sign(thief, device_keys.AUTH_CONTEXT, challenge.nonce)).to_wire(),
    )

    assert ws.closed_with is not None
    assert connection.device_id is None


async def test_a_frame_other_than_proof_after_a_challenge_is_refused(tmp_path):
    ws, conn, connection = _connection(tmp_path)
    code = pairing.mint_pairing_code(conn)
    _, pubkey = _new_key()
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,),
            device_name="pixel",
            capabilities=(),
            credential=f"pair:{code}",
            device_pubkey=pubkey,
        ).to_wire(),
    )
    await _send(connection, "heartbeat", {})
    assert ws.closed_with is not None
    assert connection.device_id is None


async def test_an_unusable_public_key_is_refused_before_any_challenge(tmp_path):
    ws, conn, connection = _connection(tmp_path)
    code = pairing.mint_pairing_code(conn)
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,),
            device_name="pixel",
            capabilities=(),
            credential=f"pair:{code}",
            device_pubkey="not-a-key",
        ).to_wire(),
    )
    assert ws.closed_with is not None
    assert not any(Envelope.from_wire(json.loads(f)).type == "challenge" for f in ws.sent)


async def test_a_node_without_a_key_still_pairs_the_pre_v04_way(tmp_path):
    """Backward compatibility: the reference node and every M2-era test omit `device_pubkey` and
    must keep the single-round-trip handshake."""
    ws, conn, connection = _connection(tmp_path)
    code = pairing.mint_pairing_code(conn)
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,), device_name="n", capabilities=(), credential=f"pair:{code}"
        ).to_wire(),
    )
    assert _last(ws).type == "welcome"
    assert Welcome.from_wire(_last(ws).payload).credential is not None


async def test_a_device_without_an_enrolled_key_reconnects_without_a_challenge(tmp_path):
    db_path = tmp_path / "registry.db"
    conn = db.connect(db_path)
    conn.execute(
        "INSERT INTO devices (device_id, friendly_name, platform, client_version, "
        "first_paired_at, last_seen_at, state) VALUES ('dev_1', 'n', 'linux', '', 0, 0, 'active')"
    )
    credential = credentials.issue_credential(conn, "dev_1")
    ws, conn, connection = _connection(tmp_path, conn)

    await _send(
        connection,
        "hello",
        Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=credential).to_wire(),
    )
    assert _last(ws).type == "welcome"
    assert connection.device_id == "dev_1"


@pytest.mark.parametrize("signature", ["", "!!!not-base64!!!", "AAAA"])
async def test_a_malformed_signature_is_refused(tmp_path, signature):
    ws, conn, connection = _connection(tmp_path)
    code = pairing.mint_pairing_code(conn)
    _, pubkey = _new_key()
    await _send(
        connection,
        "hello",
        Hello(
            hdp_versions=(0,),
            device_name="pixel",
            capabilities=(),
            credential=f"pair:{code}",
            device_pubkey=pubkey,
        ).to_wire(),
    )
    await _send(connection, "proof", {"signature": signature})
    assert ws.closed_with is not None
    assert connection.device_id is None
