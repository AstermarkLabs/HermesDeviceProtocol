"""Hermes `/hdp status|devices|audit` slash command — the **read-only** half of the operator
surface.

Delegates entirely to `cli.py`'s `render_status`/`render_devices`/`render_audit` — the same async
functions `hermes hdp` (Step 3-5) built, not a second implementation (FR-18's
surface-independence claim applies here too: two renderers, one set of logic). The one difference
from `cli.py`'s `main()`: nothing here ever calls `asyncio.run()`. Gateway mode invokes slash
commands from inside an already-running event loop, so every handler in this file is `async def
... -> str` — the returned string is this command's own output channel (Hermes sends it wherever
the invocation came from: a chat message in gateway mode, the terminal in CLI mode), never a
print. §6.1's hard rule holds here as everywhere else in this package: `ctx._cli_ref` is never
read.

**`pair` and `devices revoke` are deliberately not dispatched here (final-review finding I1).**
Both open `registry.db` and the audit log directly. That is the plan's one sanctioned exception
to Global Constraint #1 ("the plugin process never opens `registry.db`/`policy.yaml`/the audit
log/`bridge.pid`") — but the exception was reasoned for *operator CLI subcommands*: short-lived,
separate processes. This module is the opposite: in gateway mode it runs inside the
always-running plugin process, so dispatching those two here quietly extended a
separate-process exception to an in-process one, against the constraint's whole motivation (a
future separate-UID daemon, Open Q2). Every read-only verb stays available here; the two
mutating ones are answered with a pointer to `hermes hdp ...`, whose `main()` calls
`asyncio.run()` and therefore cannot execute in gateway mode's loop at all — CLI-only by
construction, not by convention.

This also removes the secondary exposure the review flagged: a plaintext pairing code is a
one-time secret, and `/hdp pair --new` would have routed it through the gateway's chat transcript
(a Discord/Slack message, persisted by the platform). It is now only ever printed to an operator's
own terminal by `hermes hdp pair --new`.
"""

from __future__ import annotations

from typing import Any

from . import cli

_USAGE = "usage: /hdp {status,devices,audit,approvals,policy}"
_CLI_ONLY = (
    "{verb} is available only from the operator CLI: run `{command}` in a terminal. "
    "It writes to the device registry and audit log directly, which the always-running "
    "plugin process must never do."
)


async def handle_hdp_command(args: str | list[str] | None = None, **kwargs: Any) -> str:
    """`args` is accepted as either a raw string (split on whitespace here) or an
    already-tokenized list — whichever convention Hermes's slash-command dispatch actually uses
    for this invocation; accepting both means this doesn't need to guess."""
    if args is None:
        argv: list[str] = []
    elif isinstance(args, str):
        argv = args.split()
    else:
        argv = list(args)
    return await _dispatch(argv)


async def _dispatch(argv: list[str]) -> str:
    if not argv:
        return _USAGE
    command, rest = argv[0], argv[1:]

    if command == "status":
        return await cli.render_status()

    if command == "devices":
        if rest and rest[0] == "revoke":
            device_id = rest[1] if len(rest) >= 2 else "<device_id>"
            return _CLI_ONLY.format(
                verb="/hdp devices revoke", command=f"hermes hdp devices revoke {device_id}"
            )
        return await cli.render_devices()

    if command == "pair":
        return _CLI_ONLY.format(verb="/hdp pair", command="hermes hdp pair --new")

    if command == "audit":
        return await cli.render_audit()

    if command == "approvals":
        if not rest or rest[0] == "list":
            return await cli.render_approvals()
        if rest[0] in {"approve", "deny"} and len(rest) >= 2:
            scope = rest[3] if len(rest) >= 4 and rest[2] == "--scope" else "one_time"
            return await cli.resolve_approval(rest[1], rest[0], scope)
        return (
            "usage: /hdp approvals {list|approve <invocation_id> [--scope <scope>]|"
            "deny <invocation_id>}"
        )

    if command == "policy":
        return await cli.render_policy(reload=bool(rest and rest[0] == "reload"))

    return f"unknown /hdp subcommand: {command!r} — {_USAGE}"


def register_command(ctx: Any) -> None:
    """Registers `/hdp` (design §2's confinement rule — this module is one of the three allowed
    to touch Hermes APIs). `handle_hdp_command` returns a string; nothing here reads
    `ctx._cli_ref` (§6.1) — every registered command renders from data returned over the control
    plane, via `cli.py`'s read-only `render_*` functions. The mutating verbs (`pair`,
    `devices revoke`) are not dispatched here at all; see this module's docstring (finding I1)."""
    ctx.register_command(
        name="hdp",
        handler=handle_hdp_command,
        description="Inspect the HDP bridge: status, devices, audit (read-only).",
    )
