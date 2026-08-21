"""The three async tool handlers. Every handler has the same shape (FR-1): `async def h(args:
dict, **kwargs) -> str`, always returns a JSON string, and **never raises**.

"Never raises" is structural, not a promise (docs/m0-plan.md §5.6): every handler is built
through `_handler`, which is the only place `except Exception` is spelled in this module. A
handler that forgot to catch would not be a subtly-wrong handler — it would be a callable that
was never wrapped, which is a much easier bug to spot in review.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

from hdp_proto.errors import ErrorCode, err, ok

from . import engine
from .runtime import capability_available, get_runtime

logger = logging.getLogger(__name__)

T = TypeVar("T")

Handler = Callable[..., Awaitable[str]]


def notifications_available() -> bool:
    """Visibility hint for ``notifications.send``; never an invocation gate.

    Hermes may cache this result for about 90 seconds. ``device_status_get`` is the authoritative
    current answer. Unknown startup state stays visible, and this synchronous read never creates
    the runtime. Invocation independently resolves live state and does not consume this snapshot.
    """
    return capability_available("notifications.send")


def echo_available() -> bool:
    """Visibility hint for ``diagnostics.echo``; never an invocation gate.

    Hermes may cache this result for about 90 seconds. ``device_status_get`` is the authoritative
    current answer. Unknown startup state stays visible, and this synchronous read never creates
    the runtime. Invocation independently resolves live state and does not consume this snapshot.
    """
    return capability_available("diagnostics.echo")


def _handler(fn: Callable[..., Awaitable[dict[str, Any]]]) -> Handler:
    """Wrap `fn` (which returns a *parsed* model-facing result dict, or raises) into a handler
    that always returns a JSON string and never raises."""

    async def h(args: dict[str, Any], **kwargs: Any) -> str:
        try:
            result = await fn(args, **kwargs)
            return json.dumps(result)
        except NotImplementedError as exc:
            # A handful of transport operations (`resolve_approval` until M3; `cancel` until it
            # was implemented at M1) raise this rather than returning a result — see
            # transport/inproc.py and transport/embedded.py's docstrings. Their `-> None`
            # signatures can't themselves produce a result-shaped error, so this is the one place
            # that raise becomes the NOT_IMPLEMENTED shape the model actually sees, instead of
            # falling through to the broader BRIDGE_UNAVAILABLE catch below.
            return json.dumps(err(ErrorCode.NOT_IMPLEMENTED, exc))
        # Deliberately broad: FR-1 forbids a handler ever raising, and a narrowed catch here is
        # exactly the hole that requirement closes.
        except Exception as exc:  # noqa: BLE001
            logger.exception("hdp handler failed")
            return json.dumps(err(ErrorCode.BRIDGE_UNAVAILABLE, exc))

    return h


async def _run_on_hdp_loop(coro: Coroutine[Any, Any, T]) -> T:
    """Run `coro` on the HDP loop and await its answer on *the caller's* loop.

    The two halves matter separately: `submit` crosses into the runtime's dedicated loop thread,
    and `asyncio.wrap_future` binds the returned future to whichever loop is running at await
    time — which is what makes one handler implementation correct under all three
    `model_tools._run_async` branches (see runtime.py's module docstring).
    """
    return await asyncio.wrap_future(get_runtime().submit(coro))


async def _notifications_send(args: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    raw = await _run_on_hdp_loop(
        engine.invoke("notifications.send", [1], args, kwargs, device_id=args.get("device"))
    )
    return json.loads(raw)


async def _status_get(args: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return await _run_on_hdp_loop(_status_get_body())


async def _status_get_body() -> dict[str, Any]:
    """Runs on the HDP loop. `device_status_get` bypasses `engine.invoke` — it reports bridge
    state rather than invoking a capability — but still succeeds with zero nodes (FR-2): an
    empty device list is information the model can act on, not an error.

    At M0 the shape is deliberately minimal — `{"ok": true, "data": {"devices": []}}` exactly,
    per the M0 exit gate (docs/m0-plan.md §8 step 6) — because there is nothing else true to
    report yet (no capabilities, no policy, no real bridge health signal). Online state,
    capabilities, and policy summary (design §2.4's full purpose for this tool) populate `data`
    as their owning milestones land real content behind them. That shape is built through
    `errors.ok` rather than spelled by hand, so it stays the one the rest of the repo emits;
    serialization is `_handler`'s job, not this function's.
    """
    devices = await get_runtime().transport.list_devices()
    return ok(
        {
            "devices": [
                {
                    "device_id": device.device_id,
                    "friendly_name": device.friendly_name,
                    "platform": device.platform,
                    "online": device.online,
                    "state": device.state,
                    "client_version": device.client_version,
                    "first_paired_at": device.first_paired_at,
                    "last_seen_at": device.last_seen_at,
                    "capabilities": [
                        {"name": capability.name, "version": capability.version}
                        for capability in device.capabilities
                    ],
                }
                for device in devices
            ]
        }
    )


async def _echo(args: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    raw = await _run_on_hdp_loop(
        engine.invoke(
            "diagnostics.echo",
            [1],
            {"payload": args.get("payload", {})},
            kwargs,
            device_id=args.get("device"),
        )
    )
    return json.loads(raw)


device_notifications_send = _handler(_notifications_send)
device_status_get = _handler(_status_get)
hdp_echo = _handler(_echo)
