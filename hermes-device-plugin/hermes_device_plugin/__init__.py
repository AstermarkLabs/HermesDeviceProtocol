"""Hermes Device Plugin package.

`register(ctx)` below, plus `cli.py` and `commands.py` which it delegates two of its calls to,
are the **only** modules in this package that import a Hermes runtime API (design §2's
confinement rule) — everything else (`engine.py`, `tools.py`, `schemas.py`, `runtime.py`,
`config.py`, `transport/`) is ordinary, host-independent Python, importable and testable by a bare
`pytest` run with no Hermes install present.
"""

from __future__ import annotations

from typing import Any

from . import cli, commands, schemas, tools


def register(ctx: Any) -> None:
    """Register the three device tools in toolset `device`, all `is_async=True` (FR-1).

    `device_status_get` carries **no** `check_fn` — deliberately, not by omission (FR-2,
    ADR-0003): it must stay model-visible precisely when nothing else works, because it is the
    recovery action `no_matching_device`'s hint names. `ctx._cli_ref` is `None` outside an
    interactive CLI run and is never touched here or in any handler — a single read of it would
    break NFR-3 (identical behaviour in CLI and gateway mode).
    """
    ctx.register_tool(
        name="device_notifications_send",
        toolset="device",
        schema=schemas.NOTIFICATIONS_SEND,
        handler=tools.device_notifications_send,
        check_fn=tools.notifications_available,
        is_async=True,
        description="Send a notification to a paired device.",
    )
    ctx.register_tool(
        name="device_status_get",
        toolset="device",
        schema=schemas.STATUS_GET,
        handler=tools.device_status_get,
        check_fn=None,  # deliberate — FR-2, ADR-0003: stays visible when nothing else works
        is_async=True,
        description="Devices, online state, capabilities, policy summary, bridge health.",
    )
    ctx.register_tool(
        name="hdp_echo",
        toolset="device",
        schema=schemas.ECHO,
        handler=tools.hdp_echo,
        check_fn=tools.echo_available,
        is_async=True,
        description="Round-trip a JSON payload to a device and back.",
    )
    # M2 Task 17: `hermes hdp {status,devices,pair,audit}` and `/hdp` — two more renderers of the
    # exact same `hdp_bridge` operations the three tools above expose to the model (FR-18's
    # surface-independence claim). Metadata-only registration, same as the tool calls above —
    # neither of these builds an `HDPRuntime` or opens a socket as a side effect of `register()`.
    cli.register_cli_command(ctx)
    commands.register_command(ctx)
