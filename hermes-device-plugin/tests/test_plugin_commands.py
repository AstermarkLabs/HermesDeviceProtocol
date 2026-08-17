"""`/hdp status|devices|pair|audit` (Task 17). Dispatch is tested against the real `cli.py`
`render_*` functions (no daemon reachable — asserting the same "cannot reach" shape `cli.py`'s own
tests exercise) plus monkeypatched stubs to prove each subcommand routes to the right renderer
with the right arguments, without needing a second full daemon fixture here — that coverage
already lives in `test_plugin_cli.py`."""

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


async def test_hdp_devices_revoke_delegates_with_the_device_id(monkeypatch):
    seen = {}

    async def _fake_revoke(device_id):
        seen["device_id"] = device_id
        return f"revoked {device_id}"

    monkeypatch.setattr(cli, "render_devices_revoke", _fake_revoke)

    out = await commands.handle_hdp_command("devices revoke dev_99")

    assert seen["device_id"] == "dev_99"
    assert out == "revoked dev_99"


async def test_hdp_devices_revoke_accepts_a_pre_tokenized_list(monkeypatch):
    async def _fake_revoke(device_id):
        return f"revoked {device_id}"

    monkeypatch.setattr(cli, "render_devices_revoke", _fake_revoke)

    out = await commands.handle_hdp_command(["devices", "revoke", "dev_5"])

    assert out == "revoked dev_5"


async def test_hdp_pair_new_delegates_to_render_pair_new(monkeypatch):
    async def _fake_pair_new():
        return "CODE-1234"

    monkeypatch.setattr(cli, "render_pair_new", _fake_pair_new)

    out = await commands.handle_hdp_command("pair --new")

    assert out == "CODE-1234"


async def test_hdp_pair_without_new_returns_usage():
    out = await commands.handle_hdp_command("pair")
    assert "usage" in out


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
