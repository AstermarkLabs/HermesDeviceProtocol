"""`register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on
device_status_get" claims, verified directly rather than inferred from a live `hermes chat -q`
run (which proves reachability, not count or check_fn identity). A fake `ctx` is sufficient:
`register()` only calls `ctx.register_tool(**kwargs)`, so this needs no Hermes install.
"""

from __future__ import annotations

import threading

import hermes_device_plugin
from hermes_device_plugin import tools


class _RecordingCtx:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.cli_commands: list[dict] = []
        self.commands: list[dict] = []

    def register_tool(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def register_cli_command(self, **kwargs) -> None:
        self.cli_commands.append(kwargs)

    def register_command(self, **kwargs) -> None:
        self.commands.append(kwargs)


def test_register_registers_exactly_three_async_device_tools():
    ctx = _RecordingCtx()
    hermes_device_plugin.register(ctx)

    by_name = {c["name"]: c for c in ctx.calls}
    assert len(ctx.calls) == 3
    assert set(by_name) == {"device_notifications_send", "device_status_get", "hdp_echo"}
    assert all(c["toolset"] == "device" for c in ctx.calls)
    assert all(c["is_async"] is True for c in ctx.calls)

    # FR-2 / ADR-0003: explicit None, not an omission — device_status_get must stay
    # model-visible when nothing else works, so it carries no health-based check_fn.
    assert by_name["device_status_get"]["check_fn"] is None
    assert by_name["device_notifications_send"]["check_fn"] is tools.runtime_healthy
    assert by_name["hdp_echo"]["check_fn"] is tools.runtime_healthy


def test_register_also_registers_the_hdp_cli_command_and_slash_command():
    """Task 17 / FR-18: two more renderers of the same underlying operations, registered
    alongside the three tools but through their own ctx APIs, not `register_tool`."""
    ctx = _RecordingCtx()
    hermes_device_plugin.register(ctx)

    assert len(ctx.cli_commands) == 1
    assert ctx.cli_commands[0]["name"] == "hdp"
    assert callable(ctx.cli_commands[0]["handler"])

    assert len(ctx.commands) == 1
    assert ctx.commands[0]["name"] == "hdp"
    assert callable(ctx.commands[0]["handler"])


def test_register_does_not_spawn_the_hdp_runtime_thread():
    """D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side effect of
    `register()` (and therefore of `hermes plugins list`) would make tool discovery force a
    thread spawn nobody asked for."""
    ctx = _RecordingCtx()
    hermes_device_plugin.register(ctx)
    assert "hdp-runtime" not in {t.name for t in threading.enumerate()}
