"""M5 Android-shaped protocol conformance.

The fixture is intentionally driven through HDP frames and the public bridge transport.  No
reference-node module, handler, or Android implementation detail is imported here.
"""

from __future__ import annotations

import asyncio
import base64

import pytest
from android_node_fixture import _ECHO_DESCRIPTOR, ANDROID_CAPABILITIES, AndroidNodeFixture
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from harness import wait_for_device
from hdp_bridge import device_keys
from hdp_bridge.enrollment import EnrollmentCoordinator
from hdp_bridge.host_identity import HostIdentityStore
from hdp_bridge.store import db
from hermes_device_plugin.transport.base import InvokeRequest

pytestmark = pytest.mark.timeout(30)


async def _wait_for_capabilities(bridge, expected: set[str]) -> None:
    deadline = asyncio.get_running_loop().time() + 5
    while asyncio.get_running_loop().time() < deadline:
        devices = await bridge.list_devices()
        online = [device for device in devices if device.online]
        if online and {capability.name for capability in online[0].capabilities} == expected:
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"capability set did not become {expected!r}")


def _usb_approved_enrollment(node: AndroidNodeFixture, hermes_home) -> str:
    """Model the already-completed physical USB + local-owner ceremony for wire conformance."""
    conn = db.connect(hermes_home / "hdp" / "registry.db")
    identifier = "android-" + "a" * 56
    coordinator = EnrollmentCoordinator(conn)
    coordinator.start(
        identifier,
        host_key_fingerprint=HostIdentityStore.load_or_create(
            hermes_home / "hdp" / "host-identity.pem"
        ).fingerprint,
        candidate_key_fingerprint=device_keys.fingerprint(node.public_key),
    )
    coordinator.approve_candidate(identifier)
    return identifier


async def test_android_profile_pair_invoke_reconnect_and_local_policy(
    bridge, bridge_url, _hermes_home
):
    node = AndroidNodeFixture()
    enrollment_id = _usb_approved_enrollment(node, _hermes_home)
    try:
        welcome = await node.connect(bridge_url, enrollment_id=enrollment_id)
        device = await wait_for_device(bridge)
        assert welcome.device_id == device.device_id
        # Amendments v0.3 — what `device_status_get` surfaces for an Android node.
        assert device.platform == "android"
        assert {capability.name for capability in device.capabilities} == {
            capability.name for capability in ANDROID_CAPABILITIES
        }

        policy_path = _hermes_home / "hdp" / "policy.yaml"
        policy_path.write_text(
            "version: 1\n"
            "defaults:\n"
            "  notifications.send: always\n"
            "  device.status: always\n"
            "  diagnostics.echo: always\n"
            "devices: {}\n"
            "default_device: {}\n",
            encoding="utf-8",
        )
        assert (await bridge.ctl_policy_reload())["ok"] is True

        status = await bridge.invoke(
            InvokeRequest("device.status", (1,), device.device_id, {}, 2_000)
        )
        assert status.ok is True
        assert status.data == {"platform": "android", "uptime_s": 0}

        notification = await bridge.invoke(
            InvokeRequest(
                "notifications.send",
                (1,),
                device.device_id,
                {"title": "M5", "body": "protocol"},
                2_000,
            )
        )
        assert notification.ok is True
        assert node.executed_notifications == [{"title": "M5", "body": "protocol"}]

        await node.replace_capabilities((_ECHO_DESCRIPTOR,))
        await _wait_for_capabilities(bridge, {"diagnostics.echo"})
        denied = await bridge.invoke(
            InvokeRequest("diagnostics.echo", (1,), device.device_id, {"payload": {}}, 2_000)
        )
        assert denied.ok is False
        assert denied.error["code"] == "policy_denied"

        reconnected = await node.reconnect(bridge_url)
        assert reconnected.device_id == device.device_id
        await _wait_for_capabilities(bridge, {"diagnostics.echo"})
    finally:
        await node.close()


async def test_android_profile_is_device_bound_end_to_end(bridge, bridge_url, _hermes_home):
    """HDP-0.md Amendments v0.4 over a real socket: enrollment proves possession of the key
    before anything is issued, and the reconnect is challenged against the stored key rather
    than trusting the credential alone."""
    node = AndroidNodeFixture()
    enrollment_id = _usb_approved_enrollment(node, _hermes_home)
    try:
        welcome = await node.connect(bridge_url, enrollment_id=enrollment_id)
        device = await wait_for_device(bridge)
        assert welcome.credential is not None

        # A credential-only reconnect is not enough: the bridge challenges, the fixture signs
        # with the enrolled key, and identity survives.
        reconnected = await node.reconnect(bridge_url)
        assert reconnected.device_id == device.device_id
        # No second credential is ever issued (FR-12) — the first welcome carried it once.
        assert reconnected.credential is None
    finally:
        await node.close()


async def test_a_node_that_cannot_sign_the_challenge_never_pairs(bridge, bridge_url, _hermes_home):
    """The stolen-code case: presenting a valid pairing code alongside a public key whose private
    half you do not hold gets no device_id and no credential."""

    class _ImpostorNode(AndroidNodeFixture):
        """Advertises an honest public key but signs with a different one."""

        def _sign_challenge(self, context: bytes, nonce: str) -> str:
            impostor = ec.generate_private_key(ec.SECP256R1())
            signature = impostor.sign(context + base64.b64decode(nonce), ec.ECDSA(hashes.SHA256()))
            return base64.b64encode(signature).decode("ascii")

    node = _ImpostorNode()
    enrollment_id = _usb_approved_enrollment(node, _hermes_home)
    try:
        with pytest.raises(Exception):  # noqa: B017 — the bridge closes the socket outright
            await node.connect(bridge_url, enrollment_id=enrollment_id)
        assert await bridge.list_devices() == []
    finally:
        await node.close()
