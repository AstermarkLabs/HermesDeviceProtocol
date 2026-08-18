"""`hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-bridge`'s operator
surface (FR-18's surface-independence claim: same underlying operations, a second renderer).

The `render_*` functions below are the actual logic. `commands.py`'s `/hdp` slash command
(Task 17 Step 6) imports and awaits these same functions rather than re-implementing anything —
one set of rendering logic, two entry points. Every `render_*` is `async def ... -> str` and
never prints: printing is `main()`'s job (this module's operator-CLI entry point), so the exact
same function also works when awaited from inside a live event loop in gateway mode (NFR-3) —
`asyncio.run()` only ever appears in `main()`, never in a function `commands.py` calls.

`status`/`devices`/`audit` go through `SocketTransport` (a fresh instance per invocation, not the
`HDPRuntime` singleton's — this is an operator diagnostic, same posture as `device_status_get`
but CLI-rendered, and must not force the runtime to build as a side effect, per D6). `pair --new`
and `devices revoke` delegate to `hdp_bridge.operations`, which owns the whole
daemon-reachable/offline-fallback decision and its audit records for both operator CLIs
(final-review finding I5) — the one place this package legitimately imports from `hdp_bridge`
(see pyproject.toml's `[tool.uv.sources]` comment). Every such import is function-local, not
module-level: this module runs as operator-invoked CLI code, not as the always-running plugin
daemon-thread code, and a module-level import would pull `hdp_bridge` into the plugin process on
every `hermes plugins list`, which is exactly the posture the brief's import exception does *not*
grant.

**Those two are reachable from this module only** (final-review finding I1). `main()` below is
the `hermes hdp` entry point and calls `asyncio.run()`, so it can only ever execute in a
short-lived operator CLI process — never inside gateway mode's already-running event loop.
`commands.py`'s `/hdp` refuses `pair`/`devices revoke` outright and points the operator here, so
the two mutating operations that open `registry.db` and the audit log directly can never run
inside the always-running plugin process (Global Constraint #1).

§6.1's hard rule, honoured throughout this file: `ctx._cli_ref` is never read, not even checked
for `None`. Every command renders from data returned over the control plane or from `hdp_bridge`'s
own persistence, never from a CLI-only Hermes rendering primitive.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any


async def render_status() -> str:
    from .transport.socket import SocketTransport

    transport = SocketTransport()
    await transport.start()
    try:
        status = await transport.status()
    finally:
        await transport.close()
    state = "healthy" if status.healthy else "unreachable"
    return f"bridge: {state} ({status.detail})" if status.detail else f"bridge: {state}"


async def render_devices() -> str:
    from .transport.socket import SocketTransport

    transport = SocketTransport()
    await transport.start()
    try:
        status = await transport.status()
        if not status.healthy:
            detail = f" ({status.detail})" if status.detail else ""
            return f"cannot reach hdp-bridge daemon{detail}"
        devices = await transport.list_devices()
    finally:
        await transport.close()
    if not devices:
        return "no paired devices"
    header = "device_id\tfriendly_name\tstate\tonline\tlast_seen_at"
    rows = [
        f"{d.device_id}\t{d.friendly_name}\t{d.state}\t"
        f"{'online' if d.online else 'offline'}\t{d.last_seen_at}"
        for d in devices
    ]
    return "\n".join([header, *rows])


async def render_pair_new() -> str:
    """CLI-only (finding I1) — `/hdp pair --new` no longer reaches this; see `commands.py`.

    A thin renderer over `hdp_bridge.operations.pair_new`, which owns the decision logic and the
    audit record (finding I5). No code, no hash, ever reaches the audit log (no-plaintext rule,
    §3.5) — only the fact that a code was minted."""
    from hdp_bridge import operations

    return await operations.pair_new()


async def render_devices_revoke(device_id: str) -> str:
    """CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see `commands.py`.

    A thin renderer over `hdp_bridge.operations.revoke` (FR-18: same operation, a second
    renderer). Everything that used to be duplicated here line-for-line against
    `hdp_bridge/cli.py` — the control-socket attempt, the offline-fallback branch, the
    `via="offline_fallback"` audit record, and the reply/rowcount checks that keep neither path
    failing open — now lives in that one module (findings I4 and I5)."""
    from hdp_bridge import operations

    return await operations.revoke(device_id)


async def render_audit() -> str:
    """Calls `ctl_audit_tail` over the control socket rather than reading
    `$HERMES_HOME/hdp/audit/` directly — keeps the surface-independent, same-verb property even
    for this read-only diagnostic (brief Step 5), and works identically whether or not this CLI
    process can see the daemon's filesystem under a different profile's permissions."""
    from .transport.socket import SocketTransport

    transport = SocketTransport()
    await transport.start()
    try:
        status = await transport.status()
        if not status.healthy:
            detail = f" ({status.detail})" if status.detail else ""
            return f"cannot reach hdp-bridge daemon{detail}"
        lines = await transport.ctl_audit_tail()
    finally:
        await transport.close()
    if not lines:
        return "no audit records for today"
    return "\n".join(json.dumps(line) for line in lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes hdp")
    subparsers = parser.add_subparsers(dest="hdp_command", required=True)
    subparsers.add_parser("status", help="Bridge health, over the control plane.")

    devices = subparsers.add_parser("devices", help="List paired devices, or revoke one.")
    devices_sub = devices.add_subparsers(dest="devices_command")
    revoke = devices_sub.add_parser("revoke", help="Revoke a paired device immediately.")
    revoke.add_argument("device_id")

    pair = subparsers.add_parser("pair", help="Pairing operations.")
    pair.add_argument("--new", action="store_true", help="Mint a new pairing code.")

    subparsers.add_parser("audit", help="Print today's audit records.")
    return parser


def _run(args: argparse.Namespace) -> str:
    if args.hdp_command == "status":
        return asyncio.run(render_status())
    if args.hdp_command == "devices":
        if getattr(args, "devices_command", None) == "revoke":
            return asyncio.run(render_devices_revoke(args.device_id))
        return asyncio.run(render_devices())
    if args.hdp_command == "pair":
        if args.new:
            return asyncio.run(render_pair_new())
        return "hermes hdp pair requires --new"
    if args.hdp_command == "audit":
        return asyncio.run(render_audit())
    raise ValueError(f"unknown hdp subcommand: {args.hdp_command!r}")  # pragma: no cover


def main(argv: list[str] | None = None) -> None:
    """The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here, never in a
    `render_*` function — this is the CLI-only caller; `commands.py`'s `/hdp` awaits the same
    `render_*` functions from inside whatever event loop Hermes's gateway mode already has
    running.

    Exits non-zero when a `devices revoke` refused or no-op'd (re-review finding I4, round 2) —
    `hdp_bridge.operations.revoke_failed` is the single source of truth for that check, shared
    with `hdp-bridge`'s own CLI so the two renderers can't drift on what counts as failure."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    message = _run(args)
    print(message)
    if (
        getattr(args, "hdp_command", None) == "devices"
        and getattr(args, "devices_command", None) == "revoke"
    ):
        from hdp_bridge import operations

        if operations.revoke_failed(message):
            raise SystemExit(1)


def register_cli_command(ctx: Any) -> None:
    """Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement rule — this
    module is one of the three allowed to touch Hermes APIs). `main` prints its own result to
    stdout — the CLI's own output channel — and never reads `ctx._cli_ref` (§6.1)."""
    ctx.register_cli_command(
        name="hdp",
        handler=main,
        description="Operate the HDP bridge: status, devices, pair, audit.",
    )
