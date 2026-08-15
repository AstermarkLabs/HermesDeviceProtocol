"""The M1 embedded aiohttp server — the counterpart of the eventual `hdp_bridge/server.py`
(ADR-0004, design §3). Lives inside the Hermes plugin process at M1; extraction to a standalone
`hdp-bridge` daemon is M2 (m1-plan.md §1's explicit non-goal: "process separation").

Routes per hdp-spec/HDP-0.md §8: `GET /hdp/v0/health` (live), `GET /hdp/v0/socket` (WebSocket
upgrade, delegates the connection lifecycle to `_connection.NodeConnection`), `POST /hdp/v0/pair`
(absent — no route registered, a 404), `/hdp/v0/blobs` (any method — reserved, `501`).

Bind lifecycle is owned by whoever constructs `EmbeddedServer` (`embedded.py`, itself started by
`HDPRuntime` on its owned loop — never by module import, per M1-1's risk mitigation in
m1-plan.md §9). `web.run_app` is never used here: it owns and creates its own event loop, which
is incompatible with running on `HDPRuntime`'s already-owned loop — `AppRunner`/`TCPSite` are the
lower-level pair that let a caller control the loop and the start/stop lifecycle explicitly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import web

from .. import config
from ._connection import NodeConnection

ConnectionFactory = Callable[[web.WebSocketResponse], NodeConnection]


def build_app(connection_factory: ConnectionFactory) -> web.Application:
    """`connection_factory` builds one `NodeConnection` per accepted WebSocket, already wired to
    the shared `RegistryMem`/`InvocationsMem`/connections/descriptors state — kept as a factory
    (rather than this module owning that state) so `EmbeddedServer` and `EmbeddedTransport` don't
    have to agree on a wider shared-state object than "how do I make one of these"."""
    app = web.Application()
    app.router.add_get("/hdp/v0/health", _health)
    app.router.add_get("/hdp/v0/socket", _make_socket_handler(connection_factory))
    app.router.add_route("*", "/hdp/v0/blobs", _blobs_reserved)
    # /hdp/v0/pair is deliberately unregistered at M1 (HDP-0.md §8) — a request there is a 404,
    # not a stub handler.
    return app


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _blobs_reserved(request: web.Request) -> web.Response:
    return web.Response(status=501, text="blobs are reserved, not implemented in the MVP")


def _make_socket_handler(
    connection_factory: ConnectionFactory,
) -> Callable[[web.Request], Coroutine[Any, Any, web.WebSocketResponse]]:
    async def handler(request: web.Request) -> web.WebSocketResponse:
        # HDP-0.md §4: WS ping/pong every 15s via aiohttp's built-in heartbeat, not a hand-rolled
        # application-level ping.
        ws = web.WebSocketResponse(heartbeat=15.0)
        await ws.prepare(request)
        connection = connection_factory(ws)
        await connection.run()
        return ws

    return handler


class EmbeddedServer:
    """Owns the `AppRunner`/`TCPSite` pair and the `bridge.addr` discovery file."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory
        self._runner: web.AppRunner | None = None

    async def start(self) -> int:
        """Bind and start serving. Returns the actually-bound port. Refuses to bind a
        non-loopback host without `HDP_ALLOW_REMOTE=1` (NFR-4) — the guard ships at M1, the
        remote-bind capability itself does not."""
        host = config.hdp_bind_host()
        if host not in ("127.0.0.1", "::1", "localhost") and not config.hdp_allow_remote():
            raise NotImplementedError(
                f"binding to non-loopback host {host!r} requires HDP_ALLOW_REMOTE=1"
            )

        app = build_app(self._connection_factory)
        runner = web.AppRunner(app)
        await runner.setup()
        # Assigned as soon as `setup()` succeeds, not after `site.start()` too: `close()` only
        # cleans up via `self._runner`, so if this coroutine is aborted between here and the
        # `return` below (e.g. `HDPRuntime.close()` racing a not-yet-finished `start()`), the
        # already-created runner must still be reachable for cleanup rather than orphaned.
        self._runner = runner
        site = web.TCPSite(runner, host, config.hdp_bind_port())
        await site.start()

        bound_port = _bound_port(site)
        await _write_bridge_addr(host, bound_port)
        return bound_port

    async def close(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        try:
            config.bridge_addr_path().unlink(missing_ok=True)
        except (KeyError, OSError):
            # Best-effort only. In production nothing ever calls `HDPRuntime.close()` (D5) — this
            # runs on the daemon "hdp-runtime" thread during the interpreter's own uncoordinated
            # shutdown at process exit, where `os.environ` (KeyError, via `config.hermes_home()`)
            # or the filesystem (OSError) may already be in a torn-down state. A stale
            # `bridge.addr` left behind is harmless: the next process's `start()` overwrites it.
            pass


def _bound_port(site: web.TCPSite) -> int:
    """`TCPSite` doesn't expose the bound port directly when the requested port was `0`
    (ephemeral) — pull it off the underlying server's sockets, the same place aiohttp itself
    reads it for its own startup log line."""
    server = site._server  # noqa: SLF001 - no public accessor; aiohttp itself has none either
    if server is None or not server.sockets:
        raise RuntimeError("TCPSite has no bound sockets after start() — server failed to bind")
    return int(server.sockets[0].getsockname()[1])


async def _write_bridge_addr(
    host: str, port: int, *, attempts: int = 3, delay_s: float = 0.1
) -> None:
    """Write `$HERMES_HOME/hdp/bridge.addr`, retrying briefly on `KeyError` (empirically: the
    real Hermes host process's own tool machinery has been observed to mutate `os.environ` from
    another thread around unrelated tool calls, occasionally landing exactly on the instant this
    reads `HERMES_HOME` — see the M1 status section of README.md). By this point the socket is
    already bound and `self._runner` already set (`EmbeddedServer.start()`'s ordering), so a
    transient failure here is worth retrying rather than tearing down an otherwise-working
    server."""
    for attempt in range(attempts):
        try:
            addr_path = config.bridge_addr_path()
            addr_path.parent.mkdir(parents=True, exist_ok=True)
            addr_path.write_text(f"{host}:{port}\n")
            return
        except KeyError:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(delay_s)
