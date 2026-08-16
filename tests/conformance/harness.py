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


async def start_node(
    bridge_url: str, *, name: str = "conformance-node", faults: tuple[str, ...] = ()
) -> asyncio.subprocess.Process:
    """Launch the real `hdp-node` CLI as a subprocess with the given `--fault` flags, pointed at
    `bridge_url`. The caller is responsible for calling `stop_node` on the result."""
    cmd = [
        sys.executable,
        "-m",
        "hdp_reference_node",
        "connect",
        "--name",
        name,
        "--url",
        bridge_url,
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
