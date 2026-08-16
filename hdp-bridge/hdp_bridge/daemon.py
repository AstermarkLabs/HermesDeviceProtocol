"""`hdp-bridge serve` — the foreground daemon entrypoint (§5.5). PID-file lifecycle hardening
(stale-socket cleanup, single-instance guard) lands in Task 15; this task is the minimal
bind/serve/shutdown loop so every task after it has a real daemon to talk to."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from . import config
from .connection import NodeConnection
from .control import ControlServer
from .invocations import InvocationsMem
from .registry import Registry
from .server import HdpServer
from .store import db as store_db


class AlreadyRunningError(RuntimeError):
    """Another live hdp-bridge process already holds this profile's PID file."""


def _pid_is_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else — treat as live, fail closed
    return True


def _check_and_claim_pid(pid_path: Path) -> None:
    """Treat `pid_path` as a *claim* to verify, not a fact to trust. If it names a live
    process, refuse to start. If it names a dead process (an unclean prior exit left it
    behind), the claim is stale — clear it and claim the file for this process instead.
    Must run before either socket binds, so a refusal never leaves a partially-started
    daemon behind."""
    if pid_path.exists():
        try:
            existing_pid = int(pid_path.read_text().strip())
        except ValueError:
            existing_pid = None
        if existing_pid is not None and _pid_is_live(existing_pid):
            raise AlreadyRunningError(
                f"hdp-bridge is already running (pid {existing_pid}, {pid_path})"
            )
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))


async def serve(*, stop_event: asyncio.Event | None = None) -> None:
    pid_path = config.pid_path()
    _check_and_claim_pid(pid_path)

    registry = Registry(config.registry_db_path())
    # NOTE — deliberate deviation from the plan's stated design: m2-plan.md describes one
    # `sqlite3.Connection` shared by `Registry`/pairing/credentials. `Registry.__init__` (Task 10,
    # already committed) instead takes a `Path` and opens its own connection internally, so there
    # is no single connection object to share. This `conn` is therefore a *second*, independent
    # `sqlite3.Connection` onto the same database file, opened purely for `NodeConnection` to hand
    # to `credentials.py`/`pairing.py` (which operate below `Registry`'s device-record API and
    # need a raw connection, not a `Registry`).
    #
    # This is safe, not merely convenient, for three concrete reasons: (1) WAL mode
    # (store/db.py's `_apply_pragmas`) makes one connection's committed writes immediately visible
    # to another connection on the same file; (2) this daemon is single-threaded and
    # single-writer (§3.2) — there is never a concurrent write racing across the two connections;
    # (3) the one place cross-connection ordering matters — `_handle_hello`'s pairing path, which
    # writes a `devices` row via `registry` before `credentials.issue_credential` writes a
    # `credentials` row via this `conn` (an FK reference) — is written in that order deliberately
    # (see `connection.py::_handle_pairing_hello`'s comment) precisely because the two connections
    # are not one transaction.
    #
    # Future work: if `Registry` ever gains an injectable `sqlite3.Connection` (rather than always
    # opening its own from a `Path`), this second `connect()` call collapses away and everything
    # converges on the single-shared-connection design the plan originally described.
    conn = store_db.connect(config.registry_db_path())
    invocations = InvocationsMem()
    connections: dict[str, NodeConnection] = {}
    descriptors: dict = {}

    def make_connection(ws: object) -> NodeConnection:
        return NodeConnection(
            ws,  # type: ignore[arg-type]
            conn=conn,
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
        conn=conn,
    )

    await hdp_server.start()
    try:
        await control.start()
    except BaseException:
        # If control.start() fails (unwritable socket path, permission error, ...), the
        # already-bound node-facing TCP socket, the `bridge.addr` file it wrote, and the PID
        # claim taken above must not leak — tear down what already succeeded before propagating.
        await hdp_server.close()
        pid_path.unlink(missing_ok=True)
        raise

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
