"""`/hdp status|devices|audit` (Task 17, narrowed by final-review finding I1). Dispatch is
tested against the real `cli.py` `render_*` functions (no daemon reachable — asserting the same
"cannot reach" shape `cli.py`'s own tests exercise) plus monkeypatched stubs, without needing a
second full daemon fixture here — that coverage already lives in `test_plugin_cli.py`.

The `pair`/`devices revoke` tests below are inverted from what they asserted before the final
review: `/hdp` must *not* reach those renderers. See finding I1 (Global Constraint #1 — the
always-running plugin process never opens `registry.db`/the audit log) and finding I2 (FR-11 —
the model can never mint a pairing code)."""

from __future__ import annotations

import pytest
from hermes_device_plugin import cli, commands


@pytest.fixture(autouse=True)
def _hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    yield tmp_path


async def test_hdp_status_delegates_to_render_status():
    out = await commands.handle_hdp_command("status")
    assert out == await cli.render_status()


async def test_hdp_devices_delegates_to_render_devices():
    out = await commands.handle_hdp_command("devices")
    assert "cannot reach hdp-bridge daemon" in out


async def test_hdp_devices_revoke_is_refused_and_never_reaches_the_renderer(monkeypatch):
    """Finding I1: `/hdp devices revoke` used to call `cli.render_devices_revoke`, which opens
    `registry.db` and the audit log — from inside the always-running plugin process in gateway
    mode. It must now refuse and point at the operator CLI instead."""

    async def _must_not_run(device_id):  # pragma: no cover — the point is that it never runs
        raise AssertionError("/hdp must not reach render_devices_revoke")

    monkeypatch.setattr(cli, "render_devices_revoke", _must_not_run)

    out = await commands.handle_hdp_command("devices revoke dev_99")

    assert "hermes hdp devices revoke dev_99" in out
    assert "only from the operator CLI" in out


async def test_hdp_devices_revoke_is_refused_for_a_pre_tokenized_list(monkeypatch):
    async def _must_not_run(device_id):  # pragma: no cover
        raise AssertionError("/hdp must not reach render_devices_revoke")

    monkeypatch.setattr(cli, "render_devices_revoke", _must_not_run)

    out = await commands.handle_hdp_command(["devices", "revoke", "dev_5"])

    assert "hermes hdp devices revoke dev_5" in out


async def test_hdp_devices_revoke_without_a_device_id_is_still_refused():
    out = await commands.handle_hdp_command("devices revoke")
    assert "only from the operator CLI" in out


async def test_hdp_pair_new_is_refused_and_never_mints_a_code(monkeypatch):
    """Finding I2 / FR-11 — "the model can never mint a pairing code".

    Two things are asserted at once: `/hdp pair --new` does not reach the minting renderer, and
    the refusal text carries no pairing code. Before this, a minted plaintext code would have
    been returned as the slash command's output — which in gateway mode is a chat message, i.e.
    a one-time secret written into a platform-persisted transcript."""

    async def _must_not_run():  # pragma: no cover — the point is that it never runs
        raise AssertionError("/hdp must not reach render_pair_new")

    monkeypatch.setattr(cli, "render_pair_new", _must_not_run)

    for argv in ("pair --new", "pair new", "pair"):
        out = await commands.handle_hdp_command(argv)
        assert "hermes hdp pair --new" in out
        assert "only from the operator CLI" in out


def test_pairing_is_not_reachable_by_any_model_invoked_tool():
    """FR-11, structurally (finding I2): no LLM-callable tool routes to pairing.

    `register()` is the *only* place this package registers model-callable tools, and the three
    it registers are the three in `tools.py`. Asserting against the real registration call — not
    against a hand-maintained list — means adding a fourth tool that could mint a pairing code
    fails this test rather than sliding past it. `/hdp` and `hermes hdp` are registered through
    `register_command`/`register_cli_command`, which are operator surfaces the model cannot
    invoke; only `register_tool` is model-reachable."""
    import hermes_device_plugin
    from hermes_device_plugin import tools

    registered_tools = []

    class _Ctx:
        def register_tool(self, **kwargs):
            registered_tools.append(kwargs)

        def register_command(self, **kwargs):
            pass

        def register_cli_command(self, **kwargs):
            pass

    hermes_device_plugin.register(_Ctx())

    assert {t["name"] for t in registered_tools} == {
        "device_notifications_send",
        "device_status_get",
        "hdp_echo",
    }
    handlers = {t["handler"] for t in registered_tools}
    assert handlers == {tools.device_notifications_send, tools.device_status_get, tools.hdp_echo}
    # And none of those three handlers is, or wraps, a pairing entry point: `cli.render_pair_new`
    # / `hdp_bridge.operations.pair_new` are reachable only from `cli.main()`, which is the
    # `hermes hdp` CLI entry point and calls `asyncio.run()` — it cannot even execute inside
    # gateway mode's already-running loop.
    assert cli.render_pair_new not in handlers


async def test_hdp_audit_delegates_to_render_audit():
    out = await commands.handle_hdp_command("audit")
    assert "cannot reach hdp-bridge daemon" in out


async def test_hdp_with_no_args_returns_usage():
    out = await commands.handle_hdp_command()
    assert "usage" in out


async def test_hdp_unknown_subcommand_is_reported_not_raised():
    out = await commands.handle_hdp_command("bogus")
    assert "unknown" in out


def test_register_command_registers_hdp():
    calls = []

    class _Ctx:
        def register_command(self, **kwargs):
            calls.append(kwargs)

    commands.register_command(_Ctx())

    assert len(calls) == 1
    assert calls[0]["name"] == "hdp"
    assert calls[0]["handler"] is commands.handle_hdp_command
