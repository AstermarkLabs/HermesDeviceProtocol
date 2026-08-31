"""Pilot coverage for the Textual operator dashboard."""

from __future__ import annotations

import pytest

textual = pytest.importorskip("textual")

from hdp_bridge import operations  # noqa: E402
from hdp_bridge.tui import HDPApp  # noqa: E402
from hdp_proto.envelope import Envelope  # noqa: E402
from rich.style import Style  # noqa: E402
from textual.widgets import DataTable, Input  # noqa: E402


async def test_dashboard_explains_usb_enrollment(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    app = HDPApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#pair")
        await pilot.pause()
        assert "Pairing codes are disabled" in str(app.screen.query_one("#pair-detail").render())
        assert app.screen.query_one(".heading").render() == "USB device enrollment"


async def test_dashboard_starts_the_daemon_usb_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    async def request(verb, payload):
        assert (verb, payload) == ("ctl_usb_bootstrap", {"serial": ""})
        return Envelope.new("ctl_usb_bootstrap_reply", {"ok": True})

    monkeypatch.setattr(operations, "control_request", request)
    app = HDPApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#pair")
        await pilot.click("#start")
        await pilot.pause()
        assert "approved" in str(app.screen.query_one("#pair-status").render())


async def test_dashboard_opens_the_paired_devices_screen(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    app = HDPApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#devices")
        await pilot.pause()
        assert app.screen.query_one("#table").render() is not None


async def test_focused_menu_button_does_not_reverse_its_label(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    app = HDPApp()

    async with app.run_test(size=(100, 30)) as pilot:
        button = app.screen.query_one("#pair")
        app.set_focus(button)
        await pilot.pause()
        assert button.styles.text_style == Style(bold=True)


def test_dashboard_hints_at_the_ctrl_q_quit_shortcut():
    assert ("ctrl+q", "quit", "Quit") in HDPApp.BINDINGS


async def test_selecting_a_device_sets_the_revoke_target(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    async def request(verb, payload):
        assert (verb, payload) == ("ctl_list_devices", {})
        return Envelope.new(
            "ctl_list_devices_reply",
            {"devices": [{"device_id": "dev_1", "friendly_name": "desk-node"}]},
        )

    monkeypatch.setattr(operations, "control_request", request)
    app = HDPApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#devices")
        await pilot.pause()
        table = app.screen.query_one("#table", DataTable)
        table.action_select_cursor()
        await pilot.pause()
        assert app.screen.query_one("#device", Input).value == "dev_1"


async def test_dashboard_opens_the_pending_approvals_screen(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    app = HDPApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#approvals")
        await pilot.pause()
        assert app.screen.query_one("#approval-status").render() is not None
