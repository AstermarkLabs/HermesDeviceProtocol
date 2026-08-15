"""`hdp-bridge serve` — the foreground daemon entrypoint (§5.5). PID-file lifecycle hardening
(stale-socket cleanup, single-instance guard) lands in Task 15; this task is the minimal
bind/serve/shutdown loop so every task after it has a real daemon to talk to."""

from __future__ import annotations

import asyncio
import os

from . import config
from .connection import NodeConnection
from .control import ControlServer
from .invocations import InvocationsMem
from .registry import RegistryMem
from .server import HdpServer


async def serve(*, stop_event: asyncio.Event | None = None) -> None:
    registry = RegistryMem()
    invocations = InvocationsMem()
    connections: dict[str, NodeConnection] = {}
    descriptors: dict = {}

    def make_connection(ws: object) -> NodeConnection:
        return NodeConnection(
            ws,  # type: ignore[arg-type]
            registry=registry,
            invocations=invocations,
            connections=connections,
            descriptors=descriptors,
        )

    hdp_server = HdpServer(
        make_connection,
        host=config.hdp_bind_host(),
        port=config.hdp_bind_port(),
        allow_remote=config.hdp_allow_remote(),
        bridge_addr_path=config.bridge_addr_path(),
    )
    control = ControlServer(
        config.control_socket_path(),
        registry=registry,
        invocations=invocations,
        connections=connections,
        descriptors=descriptors,
    )

    await hdp_server.start()
    try:
        await control.start()
    except BaseException:
        # If control.start() fails (unwritable socket path, permission error, ...), the
        # already-bound node-facing TCP socket and the `bridge.addr` file it wrote must not
        # leak — tear down what already succeeded before propagating.
        await hdp_server.close()
        raise

    pid_path = config.pid_path()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))

    stop_event = stop_event or asyncio.Event()
    try:
        await stop_event.wait()
    finally:
        await control.close()
        await hdp_server.close()
        pid_path.unlink(missing_ok=True)


def main() -> None:
    import logging
    import signal

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    stop_event = asyncio.Event()

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
        await serve(stop_event=stop_event)

    asyncio.run(_run())
