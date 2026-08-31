"""Node-subprocess helpers for the M1 conformance suite. Kept out of `conftest.py` and given a
name that can't collide with it: `hermes-device-plugin/tests/conftest.py` and this directory's
`conftest.py` are both module-scoped as bare `conftest` under pytest's rootdir-relative import
mode (neither `tests/` nor its subdirectories have `__init__.py`), so `from conftest import ...`
silently imports whichever `conftest` module Python happened to cache first when both are on
`sys.path` in the same session — a real bug, not a hypothetical one, caught by running the full
suite. A uniquely-named module sidesteps it entirely.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from pathlib import Path

from hdp_bridge import device_keys
from hdp_bridge.enrollment import EnrollmentCoordinator
from hdp_bridge.host_identity import HostIdentityStore
from hdp_bridge.store import db
from hdp_reference_node.node import _load_or_create_key, _public_key_b64
from hermes_device_plugin.transport.base import DeviceInfo
from hermes_device_plugin.transport.socket import SocketTransport


def _console_script(name: str) -> list[str]:
    """Use the active environment's installed entry point without rebuilding the workspace.

    The fallback keeps the harness usable from a source checkout where the console script has
    not been installed yet.  Using the active script directly also makes protocol tests runnable
    from an already-provisioned Hermes/uv environment with no network access.
    """
    script = Path(sys.executable).with_name(name)
    if script.exists():
        return [str(script)]
    return ["uv", "run", name]


async def start_bridge(hermes_home: Path) -> asyncio.subprocess.Process:
    """Launch the real `hdp serve` daemon as a subprocess, pointed at `hermes_home`. The
    caller is responsible for calling `stop_bridge` on the result."""
    env = {**os.environ, "HERMES_HOME": str(hermes_home), "HDP_BIND_PORT": "0"}
    proc = await asyncio.create_subprocess_exec(
        *_console_script("hdp"),
        "serve",
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    # Poll for bridge.addr to appear (same discovery file hdp-node already reads) before
    # returning, bounded — same shape as wait_for_device's polling loop below.
    addr_path = hermes_home / "hdp" / "bridge.addr"
    for _ in range(100):
        if addr_path.exists():
            return proc
        await asyncio.sleep(0.05)
    raise TimeoutError("hdp serve did not bind within 5s")


async def stop_bridge(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()


def prepare_usb_enrollment(public_key: str) -> str:
    """Model a completed local USB bootstrap for a conformance peer.

    The production bootstrap service owns USB discovery, local-owner authorization, and the
    primary-device notification.  Socket-level conformance tests deliberately begin *after*
    those physical approvals and receive only the opaque, device-bound enrollment identifier.
    """
    hermes_home = Path(os.environ["HERMES_HOME"])
    enrollment_id = uuid.uuid4().hex + uuid.uuid4().hex
    conn = db.connect(hermes_home / "hdp" / "registry.db")
    try:
        coordinator = EnrollmentCoordinator(conn)
        coordinator.start(
            enrollment_id,
            host_key_fingerprint=HostIdentityStore.load_or_create(
                hermes_home / "hdp" / "host-identity.pem"
            ).fingerprint,
            candidate_key_fingerprint=device_keys.fingerprint(public_key),
        )
        coordinator.approve_candidate(enrollment_id)
        primary = conn.execute("SELECT device_id FROM devices WHERE role = 'primary'").fetchone()
        if primary is not None:
            # The conformance harness represents the already-completed signed primary approval.
            coordinator.approve_primary(enrollment_id, primary[0])
        return enrollment_id
    finally:
        conn.close()


async def start_node(
    bridge_url: str,
    *,
    name: str = "conformance-node",
    faults: tuple[str, ...] = (),
    credential_file: Path | None = None,
    capability_versions: tuple[str, ...] = (),
) -> asyncio.subprocess.Process:
    """Launch the real `hdp-node` CLI as a subprocess with the given `--fault` flags, pointed at
    `bridge_url`. The caller is responsible for calling `stop_node` on the result.

    USB bootstrap is modeled by `prepare_usb_enrollment()` before the process starts. The opaque
    enrollment ID is bound to the generated device key. `credential_file` defaults to a name
    unique to this call
    (`os.getpid()`-scoped) rather than the CLI's own `./.hdp-node-credential` default, so
    concurrent/sequential `start_node` calls in the same test working directory never share (or
    collide over) a stored credential."""
    if credential_file is None:
        # `$HERMES_HOME` is this test's own tmp_path (the `_hermes_home` fixture) — parking the
        # credential file there, not the repo's cwd, keeps the working tree clean and gives each
        # test's node processes an isolated location regardless of run order.
        hermes_home = Path(os.environ["HERMES_HOME"])
        credential_file = hermes_home / f".hdp-node-credential.{uuid.uuid4().hex}"
    hermes_home = Path(os.environ["HERMES_HOME"])
    device_key_file = hermes_home / f".hdp-node-key.{uuid.uuid4().hex}.pem"
    public_key = _public_key_b64(_load_or_create_key(device_key_file))
    enrollment_id = prepare_usb_enrollment(public_key)
    conn = db.connect(hermes_home / "hdp" / "registry.db")
    cmd = [
        *_console_script("hdp-node"),
        "connect",
        "--name",
        name,
        "--url",
        bridge_url,
        "--enrollment-id",
        enrollment_id,
        "--credential-file",
        str(credential_file),
        "--device-key-file",
        str(device_key_file),
    ]
    for flag in faults:
        cmd += ["--fault", flag]
    for capability_version in capability_versions:
        cmd += ["--capability-version", capability_version]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    for _ in range(100):
        row = conn.execute(
            "SELECT state FROM pending_enrollments WHERE identifier_hash = ?",
            (hashlib.sha256(enrollment_id.encode("ascii")).hexdigest(),),
        ).fetchone()
        if row is not None and row[0] == "consumed":
            return proc
        await asyncio.sleep(0.05)
    await stop_node(proc)
    raise TimeoutError("reference node did not consume its USB enrollment within 5s")


async def stop_node(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()


async def wait_for_device(bridge: SocketTransport, *, timeout_s: float = 10.0) -> DeviceInfo:
    """Poll `bridge.list_devices()` until at least one device is online, or raise on timeout."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        devices = await bridge.list_devices()
        online = [d for d in devices if d.online]
        if online:
            return online[0]
        await asyncio.sleep(0.05)
    raise TimeoutError("no node connected within the timeout")


async def wait_for_log(
    lines: list[str],
    substring: str,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109 — a polling deadline, not a cancellation scope
) -> None:
    """Poll the `bridge_log` list (conftest.py's live-updated capture of the `hdp serve`
    subprocess's stdout) until `substring` appears, or raise on timeout.

    Exists because a bridge-side log line and an `invoke()` return value travel two *independent*
    paths: the reply comes back over the control socket, while the log line goes daemon stdout ->
    OS pipe -> conftest's `_drain()` task -> `lines`. Nothing synchronizes the two, so asserting
    on `lines` immediately after `await bridge.invoke(...)` returns is a race the test loses
    whenever the drain task hasn't been scheduled yet. Polling closes it.

    ASYNC109 wants `asyncio.timeout` instead of a `timeout` parameter. That rule is aimed at
    functions that pass a timeout down to a single awaited operation; this one has no such
    operation to wrap — it is a poll loop over a plain list, and the parameter names how long to
    keep polling. `asyncio.timeout` here would only replace a specific failure message ("X never
    appeared in the bridge log") with a bare `TimeoutError`.

    Lives in `harness.py` rather than `conftest.py` (which is where the review filed it) for the
    reason this module's own docstring gives: `from conftest import ...` is not safe in this
    suite — two different `conftest` modules collide under pytest's rootdir-relative import mode.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if substring in "".join(lines):
            return
        await asyncio.sleep(0.02)
    raise TimeoutError(f"{substring!r} never appeared in the bridge log within {timeout}s")
