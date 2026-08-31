"""Protocol-only Android-shaped node fixture for the M5 conformance target.

This fixture deliberately does not import ``hdp_reference_node``.  It models the wire and
observable policy boundary an Android implementation must satisfy, while keeping Android
runtime APIs out of this repository's Python test process.
"""

from __future__ import annotations

import asyncio
import base64
import json

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.messages import CapabilitiesMsg, Challenge, Hello, Proof, ResultMsg, Welcome

#: Mirrors `hdp_bridge.device_keys`' contexts. Deliberately re-stated rather than imported: this
#: fixture models a *peer*, and a peer gets these from the spec (HDP-0.md Amendments v0.4), not
#: from the bridge's own module. Importing them would let a rename on one side silently keep the
#: test passing while every real node broke.
_PAIR_CONTEXT = b"HDP/0 pair-challenge\x00"
_AUTH_CONTEXT = b"HDP/0 auth-challenge\x00"

ANDROID_CAPABILITIES = (
    CapabilityDescriptor(
        name="notifications.send",
        version=1,
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title", "body"],
        },
        output_schema={
            "type": "object",
            "properties": {"delivered": {"type": "boolean"}},
            "required": ["delivered"],
        },
    ),
    CapabilityDescriptor(
        name="device.status",
        version=1,
        input_schema={"type": "object", "properties": {}},
        output_schema={
            "type": "object",
            "properties": {"platform": {"type": "string"}, "uptime_s": {"type": "number"}},
            "required": ["platform", "uptime_s"],
        },
    ),
)

_ECHO_DESCRIPTOR = CapabilityDescriptor(
    name="diagnostics.echo",
    version=1,
    input_schema={"type": "object"},
    output_schema={"type": "object"},
)


class AndroidNodeFixture:
    """A small HDP peer with Android M5 policy semantics.

    The fixture stores the credential and private key in memory only.  A real Android node must
    replace both with Keystore-protected storage as specified in
    ``docs/android-node-contract.md``.

    It implements the v0.4 device-bound handshake because that is what the Android profile
    requires, which also gives challenge/proof its only coverage over a real socket.
    """

    def __init__(self, name: str = "android-fixture") -> None:
        self.name = name
        self.credential: str | None = None
        self.device_id: str | None = None
        self.capabilities = ANDROID_CAPABILITIES
        self.executed_notifications: list[dict[str, str]] = []
        self.revoked = False
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._cancelled: set[str] = set()
        self._private_key = ec.generate_private_key(ec.SECP256R1())

    @property
    def public_key(self) -> str:
        """Base64 DER SubjectPublicKeyInfo, the encoding `hello.device_pubkey` carries."""
        return base64.b64encode(
            self._private_key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).decode("ascii")

    def _sign_challenge(self, context: bytes, nonce: str) -> str:
        """Sign the context prefix followed by the *decoded* nonce bytes (HDP-0.md v0.4) — not
        the base64 text, which would produce a well-formed signature that never verifies."""
        signature = self._private_key.sign(
            context + base64.b64decode(nonce), ec.ECDSA(hashes.SHA256())
        )
        return base64.b64encode(signature).decode("ascii")

    async def connect(self, url: str, *, enrollment_id: str | None = None) -> Welcome:
        """Connect and complete pairing or credential authentication."""
        if self._reader_task is not None:
            await self.close()
        if self.revoked:
            raise RuntimeError("revoked fixture cannot reconnect")

        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(url, heartbeat=15.0)
        pairing = enrollment_id is not None
        credential = None if pairing else self.credential
        hello = Hello(
            hdp_versions=(0,),
            device_name=self.name,
            capabilities=self.capabilities,
            credential=credential,
            # Amendments v0.3. The reference node deliberately omits this, so the suite keeps
            # live coverage of both the reporting and the omitting branch.
            platform="android",
            # Amendments v0.4: only the enrolling `hello` carries the key; afterwards the bridge
            # challenges against the key it already stored.
            device_pubkey=self.public_key if pairing else None,
            enrollment_id=enrollment_id,
        )
        await self._send(Envelope.new("hello", hello.to_wire()))

        envelope = await self._receive()
        if envelope.type == "challenge":
            nonce = Challenge.from_wire(envelope.payload).nonce
            context = _PAIR_CONTEXT if pairing else _AUTH_CONTEXT
            await self._send(
                Envelope.new(
                    "proof", Proof(signature=self._sign_challenge(context, nonce)).to_wire()
                )
            )
            envelope = await self._receive()

        if envelope.type != "welcome":
            raise RuntimeError(f"expected welcome, got {envelope.type!r}")
        welcome = Welcome.from_wire(envelope.payload)
        self.device_id = welcome.device_id
        if welcome.credential is not None:
            self.credential = welcome.credential
        self._reader_task = asyncio.create_task(self._read_frames())
        return welcome

    async def _receive(self) -> Envelope:
        assert self._ws is not None
        message = await self._ws.receive(timeout=5)
        if message.type != aiohttp.WSMsgType.TEXT:
            raise RuntimeError(f"expected a text frame, got {message.type!r}")
        return Envelope.from_wire(json.loads(message.data))

    async def reconnect(self, url: str) -> Welcome:
        """Reconnect with the stored credential and preserve the bridge-issued identity."""
        if self.credential is None:
            raise RuntimeError("fixture has not been paired")
        await self.close()
        return await self.connect(url)

    async def replace_capabilities(self, capabilities: tuple[CapabilityDescriptor, ...]) -> None:
        """Send a complete capability replacement, matching FR-8."""
        self.capabilities = capabilities
        await self._send(Envelope.new("capabilities", CapabilitiesMsg(capabilities).to_wire()))

    async def close(self) -> None:
        """Close the current connection and reap its reader task."""
        task, self._reader_task = self._reader_task, None
        if self._ws is not None:
            await self._ws.close()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        if self._session is not None:
            await self._session.close()
        self._ws = None
        self._session = None

    async def _read_frames(self) -> None:
        assert self._ws is not None
        async for message in self._ws:
            if message.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                envelope = Envelope.from_wire(json.loads(message.data))
            except (ValueError, EnvelopeError):
                continue
            if envelope.type == "invoke":
                asyncio.create_task(self._handle_invoke(envelope))
            elif envelope.type == "cancel" and envelope.corr:
                self._cancelled.add(envelope.corr)
            elif envelope.type == "heartbeat":
                await self._send(Envelope.new("heartbeat", {}))
            elif envelope.type == "revoke":
                self.revoked = True
                await self._ws.close()
                return

    async def _handle_invoke(self, envelope: Envelope) -> None:
        invocation_id = envelope.corr
        capability = envelope.payload.get("capability")
        args = envelope.payload.get("args", {})
        await self._send(Envelope.new("ack", {}, corr=invocation_id))
        if invocation_id in self._cancelled:
            self._cancelled.discard(invocation_id)
            return

        if capability not in {item.name for item in self.capabilities}:
            result = ResultMsg(
                ok=False,
                data=None,
                error={
                    "code": "policy_denied",
                    "message": f"Android local policy denies {capability!r}",
                    "hint": "Enable the capability in the Android node policy and retry.",
                },
            )
        elif capability == "notifications.send":
            self.executed_notifications.append({"title": args["title"], "body": args["body"]})
            result = ResultMsg(ok=True, data={"delivered": True}, error=None)
        elif capability == "device.status":
            result = ResultMsg(ok=True, data={"platform": "android", "uptime_s": 0}, error=None)
        else:
            result = ResultMsg(ok=False, data=None, error={"code": "policy_denied"})
        await self._send(Envelope.new("result", result.to_wire(), corr=invocation_id))

    async def _send(self, envelope: Envelope) -> None:
        if self._ws is None:
            raise RuntimeError("fixture is not connected")
        await self._ws.send_str(json.dumps(envelope.to_wire()))
