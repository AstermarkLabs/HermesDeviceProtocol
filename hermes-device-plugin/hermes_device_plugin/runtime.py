"""`HDPRuntime` — the pattern the whole architecture bets on (ADR-0002, docs/m0-plan.md §6).

`model_tools._run_async` (`~/.hermes/hermes-agent/model_tools.py:103`) hands a tool handler a
**different** event loop on each of three branches — a disposable thread's fresh loop (already-
running-loop callers, e.g. gateway mode), a persistent shared loop (CLI), or a per-thread
persistent loop (worker threads) — and the loop from branch 1 is destroyed the instant the call
returns. Anything bound to *that* loop dies with it. HDP needs long-lived state (a WebSocket
server at M1, a pending-invocation table throughout), so it cannot live on a handler's loop.

The fix: HDP owns one dedicated daemon thread with its own event loop, created exactly once
behind `lazy_singleton` (mandatory, not stylistic — a hand-rolled `global` + `is None` check is a
reachable TOCTOU under Hermes's multi-threaded calling contexts, and would create two loop
threads racing over one port from M1 onward). Every handler crosses the thread boundary with
`asyncio.wrap_future`, which binds to *the caller's* loop at await time — not at import time, not
at registration time — which is what makes one implementation correct under all three branches
and is the mechanism behind NFR-3 (identical CLI/gateway behaviour).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

try:
    from plugins.plugin_utils import lazy_singleton
except ImportError:  # pragma: no cover — bare `pytest` runs with no Hermes on sys.path
    from ._singleton import lazy_singleton

from .transport.base import BridgeTransport
from .transport.embedded import EmbeddedTransport

T = TypeVar("T")

_HDP_THREAD_NAME = "hdp-runtime"


class HDPRuntime:
    """Owns a daemon thread and the `asyncio` loop running on it. Constructed exactly once per
    process by `get_runtime()` below — never construct this directly."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._close_requested = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.transport: BridgeTransport = EmbeddedTransport()
        self._thread = threading.Thread(target=self._run_loop, name=_HDP_THREAD_NAME, daemon=True)
        self._thread.start()
        self._ready.wait()

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_until_complete(self._serve_until_close_requested())
        finally:
            loop.run_until_complete(self.transport.close())
            loop.close()

    async def _serve_until_close_requested(self) -> None:
        """`await self.transport.start()` runs to completion before anything checks
        `_close_requested` — deliberately, not incidentally. An earlier version signalled
        shutdown by calling `loop.stop()` from `close()` (the other thread) via
        `call_soon_threadsafe`; if that fired while `transport.start()` was still mid-flight (the
        realistic case when `close()` is called immediately after construction — exactly what
        tests/conformance/test_runtime_composition.py does every iteration), `run_until_complete`
        raised `RuntimeError: Event loop stopped before Future completed`, abandoning `start()`'s
        coroutine in an unknown partial state — sometimes leaving a bound socket whose `AppRunner`
        was never assigned anywhere `close()` could reach, which is a real fd/thread leak, not a
        merely slow one. Polling a plain `threading.Event` after `start()` has already returned
        makes early-`close()` a no-op race instead of an abort: `close()` can set the flag at any
        time, including before `start()` even begins, and this coroutine simply won't look at it
        until `start()` is done."""
        await self.transport.start()
        # noqa: ASYNC110 — ruff's suggested fix (`asyncio.Event`) isn't safe here: `close()` sets
        # `_close_requested` from a *different OS thread*, and `asyncio.Event.set()` is not
        # thread-safe without routing through `call_soon_threadsafe` — which is exactly the
        # cross-thread scheduling this method exists to avoid depending on (see the docstring
        # above). A `threading.Event`, polled, is the correct primitive for a flag set from
        # another thread and read from a coroutine.
        while not self._close_requested.is_set():  # noqa: ASYNC110
            await asyncio.sleep(0.05)

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        loop = self._loop  # always set by the time `_ready` fires — `__init__` blocks on it
        if loop is None:
            raise RuntimeError("HDPRuntime loop is not initialized")
        return loop

    def submit(self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Schedule `coro` onto the HDP loop from any thread. Returns a plain
        `concurrent.futures.Future` with no loop affinity — callers bind it to *their own* loop
        with `await asyncio.wrap_future(fut)` at await time (the trick that makes this correct
        under all three `_run_async` branches)."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def close(self, *, timeout: float = 10.0) -> None:
        """Explicit teardown for tests (`lazy_singleton`'s `.reset()` only drops the cached
        instance; it does not stop the thread). Production has no equivalent call site — the HDP
        thread is a daemon thread specifically so a hung transport can never wedge `hermes` on
        exit (D5, docs/m0-plan.md §6.5).

        Safe to call at any time, including immediately after construction, before `start()` has
        even begun — see `_serve_until_close_requested`'s docstring for why that used to matter."""
        self._close_requested.set()
        self._thread.join(timeout=timeout)


@lazy_singleton
def get_runtime() -> HDPRuntime:
    """The one `HDPRuntime` for this process, built at first use. Do not call this from a
    `check_fn` — see `tools.runtime_healthy`, which must not force construction (D6)."""
    return HDPRuntime()
