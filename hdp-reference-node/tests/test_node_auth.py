"""The reference node's M2 auth behaviour (final-review findings I7 and I8).

Driven against a real `aiohttp` WebSocket server standing in for the bridge, not a monkeypatched
`node` module — same discipline as the conformance suite (m1-plan.md §9): the node's misbehaviour
and the bridge's responses are both real wire traffic.
"""

from __future__ import annotations

import asyncio
import json
import stat

import aiohttp
import pytest
from aiohttp import web
from hdp_proto.envelope import Envelope
from hdp_proto.messages import Welcome
from hdp_reference_node import node
from hdp_reference_node.faults import FaultConfig


async def test_local_policy_refusal_returns_policy_denied():
    """M3's node-side enforcement has the same policy-denial contract as the bridge."""
    session = node._NodeSession(None, FaultConfig())  # type: ignore[arg-type]

    result = await session._build_result("camera.capture", {})

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "policy_denied"


async def _serve(handler) -> tuple[web.AppRunner, str]:
    app = web.Application()
    app.router.add_get("/hdp/v0/socket", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, f"ws://127.0.0.1:{port}/hdp/v0/socket"


@pytest.fixture
async def bridge_stub(request):
    runner, url = await _serve(request.param)
    try:
        yield url
    finally:
        await runner.cleanup()


async def _auth_failed_handler(request):
    """What `hdp_bridge/connection.py` really does on every `auth_failed` path: close with
    `POLICY_VIOLATION`, send no reply frame."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.receive()  # the hello
    await ws.close(code=aiohttp.WSCloseCode.POLICY_VIOLATION, message=b"auth_failed")
    return ws


@pytest.mark.parametrize("bridge_stub", [_auth_failed_handler], indirect=True)
async def test_auth_failed_is_terminal_and_never_retried(bridge_stub, tmp_path, caplog):
    """Finding I7.3, the whole bug in one line: the old code raised `ConnectionError`, which is an
    `OSError` subclass, so `run()`'s `except (aiohttp.ClientError, OSError)` caught it and retried
    forever with the same rejected credential. `AuthFailed` must escape that handler.

    `max_reconnect_attempts=5` gives retrying somewhere to go: if the bug were still present this
    would burn five attempts (and >1s of jittered backoff) before raising — instead it must raise
    `AuthFailed` on the very first one.
    """
    credential_file = tmp_path / "cred"
    credential_file.write_text("a-revoked-credential")

    loop = asyncio.get_running_loop()
    start = loop.time()
    with pytest.raises(node.AuthFailed):
        await node.run(
            bridge_stub,
            "test-node",
            FaultConfig(),
            credential_file=credential_file,
            max_reconnect_attempts=5,
        )
    elapsed = loop.time() - start

    assert elapsed < 1.0, f"auth_failed was retried ({elapsed:.2f}s spent backing off)"
    assert not isinstance(node.AuthFailed(), OSError), (
        "AuthFailed must not be an OSError subclass, or run()'s reconnect handler swallows it"
    )


async def _abrupt_close_handler(request):
    """A genuine network-ish failure — a close with no auth semantics at all. Must still be
    retried, so the I7.3 fix doesn't turn every disconnect into a terminal one."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.receive()
    await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message=b"bye")
    return ws


@pytest.mark.parametrize("bridge_stub", [_abrupt_close_handler], indirect=True)
async def test_a_non_auth_close_is_still_retried(bridge_stub, tmp_path):
    credential_file = tmp_path / "cred"
    credential_file.write_text("a-fine-credential")

    with pytest.raises(ConnectionError):
        await node.run(
            bridge_stub,
            "test-node",
            FaultConfig(),
            credential_file=credential_file,
            max_reconnect_attempts=2,
        )


async def _pairing_handler(request):
    """Completes a first-time pairing and issues a credential, then holds the socket open."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.receive()  # the hello
    welcome = Welcome(hdp_version=0, device_id="01JB0000000000000000000000", credential="s3cret")
    await ws.send_str(json.dumps(Envelope.new("welcome", welcome.to_wire()).to_wire()))
    await ws.close()
    return ws


@pytest.mark.parametrize("bridge_stub", [_pairing_handler], indirect=True)
async def test_the_issued_credential_is_written_0600(bridge_stub, tmp_path):
    """Finding I7.1: `Path.write_text` created this file at the process umask — typically 0644,
    i.e. a long-lived device secret readable by every user on the machine."""
    credential_file = tmp_path / "cred"

    await node.run(
        bridge_stub, "test-node", FaultConfig(), pair_code="CODE", credential_file=credential_file
    )

    assert credential_file.read_text() == "s3cret"
    assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600


@pytest.mark.parametrize("bridge_stub", [_pairing_handler], indirect=True)
async def test_re_pairing_over_a_world_readable_file_still_ends_at_0600(bridge_stub, tmp_path):
    """`O_CREAT`'s mode argument is ignored when the file already exists — which is exactly the
    re-pairing case. The `fchmod` on the open descriptor is what covers it."""
    credential_file = tmp_path / "cred"
    credential_file.write_text("an-old-credential")
    credential_file.chmod(0o644)

    await node.run(
        bridge_stub, "test-node", FaultConfig(), pair_code="CODE", credential_file=credential_file
    )

    assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600


async def _revoking_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.receive()  # the hello
    welcome = Welcome(hdp_version=0, device_id="01JB0000000000000000000000", credential=None)
    await ws.send_str(json.dumps(Envelope.new("welcome", welcome.to_wire()).to_wire()))
    await ws.send_str(
        json.dumps(Envelope.new("revoke", {"reason": "revoked by operator"}).to_wire())
    )
    await ws.receive()  # the node's close
    return ws


@pytest.mark.parametrize("bridge_stub", [_revoking_handler], indirect=True)
async def test_a_revoke_frame_ends_the_session_without_reconnecting(bridge_stub, tmp_path, caplog):
    """Finding I7.2: `revoke` used to be a documented no-op ("no action needed ... at M1"), but
    M2's HDP-0.md Amendments (v0.2) make it a real frame the bridge sends on operator revocation.
    The node must log it and stop — not sit on a dead connection, and not reconnect with the
    credential that was just invalidated.

    `max_reconnect_attempts=3` means a reconnect attempt would hit `_revoking_handler` again and
    the test would take three times as long; returning cleanly is what makes it fast.
    """
    credential_file = tmp_path / "cred"
    credential_file.write_text("about-to-be-revoked")

    with caplog.at_level("ERROR"):
        await asyncio.wait_for(
            node.run(
                bridge_stub,
                "test-node",
                FaultConfig(),
                credential_file=credential_file,
                max_reconnect_attempts=3,
            ),
            timeout=10,
        )

    assert "revoked by the bridge" in caplog.text


def test_backoff_starts_at_one_second_is_capped_at_thirty_and_is_jittered():
    """FR-14, which the previous `min(30.0, 0.5 * (2 ** (attempt - 1)))` met on none of the three
    counts: it started at 0.5s, and its complete absence of jitter meant N nodes reconnecting to
    a restarted bridge retried in permanent lockstep (finding I8)."""
    first = [node._backoff_delay(1) for _ in range(50)]
    assert all(1.0 <= d <= 1.25 for d in first), "attempt 1 must be 1s plus up to 25% jitter"
    assert len(set(first)) > 1, "no jitter — every attempt returns an identical delay"

    assert all(2.0 <= node._backoff_delay(2) <= 2.5 for _ in range(20))
    assert all(4.0 <= node._backoff_delay(3) <= 5.0 for _ in range(20))
    # The ceiling applies to the exponential *base*, not to the jittered result — jitter must
    # keep spreading attempts out even at the ceiling, or N nodes converge back into lockstep at
    # steady state, which is the exact condition this backoff exists to prevent (re-review
    # finding, round 2: an earlier version clamped the sum too, so every attempt >= ~6 returned
    # exactly 30.0).
    at_ceiling = [node._backoff_delay(attempt) for attempt in (6, 10, 20) for _ in range(20)]
    assert all(30.0 <= d <= 30.0 + 30.0 * node._BACKOFF_JITTER_FRACTION for d in at_ceiling)
    assert len(set(at_ceiling)) > 1, "no jitter at the ceiling — attempts are back in lockstep"
