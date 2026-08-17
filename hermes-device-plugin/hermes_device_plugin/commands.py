"""Hermes `/hdp status|devices|pair|audit` slash command.

Delegates entirely to `cli.py`'s `render_status`/`render_devices`/`render_pair_new`/
`render_devices_revoke`/`render_audit` — the same async functions `hermes hdp` (Step 3-5) built,
not a second implementation (FR-18's surface-independence claim applies here too: two renderers,
one set of logic). The one difference from `cli.py`'s `main()`: nothing here ever calls
`asyncio.run()`. Gateway mode invokes slash commands from inside an already-running event loop, so
every handler in this file is `async def ... -> str` — the returned string is this command's own
output channel (Hermes sends it wherever the invocation came from: a chat message in gateway
mode, the terminal in CLI mode), never a print. §6.1's hard rule holds here as everywhere else in
this package: `ctx._cli_ref` is never read.
"""

from __future__ import annotations

from typing import Any

from . import cli

_USAGE = "usage: /hdp {status,devices,pair,audit}"


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
        if len(rest) >= 2 and rest[0] == "revoke":
            return await cli.render_devices_revoke(rest[1])
        return await cli.render_devices()

    if command == "pair":
        if "--new" in rest or "new" in rest:
            return await cli.render_pair_new()
        return "usage: /hdp pair --new"

    if command == "audit":
        return await cli.render_audit()

    return f"unknown /hdp subcommand: {command!r} — {_USAGE}"


def register_command(ctx: Any) -> None:
    """Registers `/hdp` (design §2's confinement rule — this module is one of the three allowed
    to touch Hermes APIs). `handle_hdp_command` returns a string; nothing here reads
    `ctx._cli_ref` (§6.1) — every command renders from data returned over the control plane or
    from `hdp_bridge`'s own persistence, via `cli.py`'s `render_*` functions."""
    ctx.register_command(
        name="hdp",
        handler=handle_hdp_command,
        description="Operate the HDP bridge: status, devices, pair, audit.",
    )
