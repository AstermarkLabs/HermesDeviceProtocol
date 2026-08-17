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
import os
import sys
import uuid
from pathlib import Path

from hermes_device_plugin.transport.base import DeviceInfo
from hermes_device_plugin.transport.socket import SocketTransport


async def start_bridge(hermes_home: Path) -> asyncio.subprocess.Process:
    """Launch the real `hdp-bridge serve` daemon as a subprocess, pointed at `hermes_home`. The
    caller is responsible for calling `stop_bridge` on the result."""
    env = {**os.environ, "HERMES_HOME": str(hermes_home), "HDP_BIND_PORT": "0"}
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "hdp-bridge",
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
    raise TimeoutError("hdp-bridge serve did not bind within 5s")


async def stop_bridge(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()


async def mint_pairing_code() -> str:
    """Run `hdp-bridge pair new` as a subprocess against the already-running bridge daemon
    (`$HERMES_HOME` is already set for this test by the `_hermes_home` fixture, and both this
    subprocess and the daemon's own connection see the same SQLite file — WAL mode makes that
    safe) and return the minted pairing code. M2: every node connection now needs one of these
    before it can complete a `hello` handshake — see `start_node`'s docstring."""
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "hdp-bridge",
        "pair",
        "new",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"hdp-bridge pair new failed: {stderr.decode(errors='replace')}")
    return stdout.decode().strip()


async def start_node(
    bridge_url: str,
    *,
    name: str = "conformance-node",
    faults: tuple[str, ...] = (),
    credential_file: Path | None = None,
) -> asyncio.subprocess.Process:
    """Launch the real `hdp-node` CLI as a subprocess with the given `--fault` flags, pointed at
    `bridge_url`. The caller is responsible for calling `stop_node` on the result.

    M2: the bridge no longer accepts an unpaired `hello` (hdp-spec/HDP-0.md's Amendments (v0.2)),
    so this mints a fresh one-time pairing code for every call via `mint_pairing_code()` and
    passes it as `--pair-code`. `credential_file` defaults to a name unique to this call
    (`os.getpid()`-scoped) rather than the CLI's own `./.hdp-node-credential` default, so
    concurrent/sequential `start_node` calls in the same test working directory never share (or
    collide over) a stored credential."""
    if credential_file is None:
        # `$HERMES_HOME` is this test's own tmp_path (the `_hermes_home` fixture) — parking the
        # credential file there, not the repo's cwd, keeps the working tree clean and gives each
        # test's node processes an isolated location regardless of run order.
        hermes_home = Path(os.environ["HERMES_HOME"])
        credential_file = hermes_home / f".hdp-node-credential.{uuid.uuid4().hex}"
    pair_code = await mint_pairing_code()
    cmd = [
        sys.executable,
        "-m",
        "hdp_reference_node",
        "connect",
        "--name",
        name,
        "--url",
        bridge_url,
        "--pair-code",
        pair_code,
        "--credential-file",
        str(credential_file),
    ]
    for flag in faults:
        cmd += ["--fault", flag]
    return await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )


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
    """Poll the `bridge_log` list (conftest.py's live-updated capture of the `hdp-bridge serve`
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
