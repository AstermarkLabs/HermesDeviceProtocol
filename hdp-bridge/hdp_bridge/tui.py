"""Textual operator dashboard; it renders existing HDP operations, not a new control plane."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from . import config, operations
from .policy import PolicyEngine
from .registry import Registry


def _when(value: object) -> str:
    return (
        datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d %H:%M")
        if isinstance(value, int) and value
        else "—"
    )


class Base(Screen[None]):
    def menu(self) -> None:
        self.app.switch_screen(Menu())

    async def request(self, verb: str, payload: dict) -> tuple[dict | None, str | None]:
        reply = await operations.control_request(verb, payload)
        return (
            (reply.payload, None)
            if reply.type != "error"
            else (None, str(reply.payload.get("message", "bridge unavailable")))
        )


class Menu(Base):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("HDP operator dashboard", id="title")
        yield Static(f"Profile: {config.hermes_home()}", id="profile")
        with Vertical(id="menu"):
            for label, ident in (
                ("Bridge status", "status"),
                ("Pair a device", "pair"),
                ("Paired devices", "devices"),
                ("Pending approvals", "approvals"),
                ("Audit log", "audit"),
                ("Policy", "policy"),
            ):
                yield Button(label, id=ident, variant="primary" if ident == "status" else "default")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        screens = {
            "status": Status(),
            "pair": Pair(),
            "devices": Devices(),
            "approvals": Approvals(),
            "audit": Audit(),
            "policy": Policy(),
        }
        self.app.switch_screen(screens[event.button.id or "status"])


class Status(Base):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Bridge status", classes="heading")
        yield Static("Checking…", id="result")
        yield Static(
            "The dashboard never starts or stops the daemon. Start it separately with `hdp serve`.",
            classes="hint",
        )
        yield Button("Menu", id="menu")
        yield Footer()

    async def on_mount(self) -> None:
        payload, error = await self.request("ctl_status", {})
        self.query_one("#result", Static).update(
            f"● Online — {payload.get('detail')}" if payload else f"● Offline — {error}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.menu()


class Pair(Base):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("USB device enrollment", classes="heading")
        yield Static(
            "Connect the new device by USB, then complete local owner authentication. "
            "The primary device must approve each secondary-device enrollment.",
            id="pair-status",
        )
        with Horizontal():
            yield Button("Start USB bootstrap", id="start", variant="success")
            yield Button("Menu", id="menu")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "menu":
            self.menu()
            return
        self.query_one("#pair-status", Static).update(
            "Waiting for Android USB accessory and local owner authorization…"
        )
        _, error = await self.request("ctl_usb_bootstrap", {"serial": ""})
        self.query_one("#pair-status", Static).update(
            error or "USB bootstrap approved; complete enrollment on the device."
        )

class Devices(Base):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Paired devices", classes="heading")
        yield Static("", id="devices-status")
        yield DataTable(id="table", cursor_type="row")
        yield Input(placeholder="Device ID to revoke", id="device")
        with Horizontal():
            yield Button("Revoke", id="revoke", variant="error")
            yield Button("Refresh", id="refresh")
            yield Button("Menu", id="menu")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#table", DataTable).add_columns(
            "Name", "Platform", "Device ID", "State", "Online", "Paired", "Last seen", "Caps"
        )
        await self.load_devices()

    async def load_devices(self) -> None:
        payload, error = await self.request("ctl_list_devices", {})
        devices = (
            payload.get("devices", [])
            if payload
            else [x.to_wire() for x in Registry(config.registry_db_path()).list_devices()]
        )
        self.query_one("#devices-status", Static).update(
            "Live daemon data" if payload else f"Offline — durable records only ({error})"
        )
        table = self.query_one("#table", DataTable)
        table.clear()
        for x in devices:
            table.add_row(
                str(x.get("friendly_name")),
                str(x.get("platform")),
                str(x.get("device_id")),
                str(x.get("state", "active")),
                "●" if x.get("online") else "○",
                _when(x.get("first_paired_at")),
                _when(x.get("last_seen_at")),
                str(len(x.get("capabilities", []))),
                key=str(x.get("device_id", "")),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.query_one("#device", Input).value = str(event.row_key.value)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "menu":
            self.menu()
        elif event.button.id == "refresh":
            await self.load_devices()
        elif event.button.id == "revoke":
            ident = self.query_one("#device", Input).value.strip()
            if ident:
                self.app.switch_screen(Revoke(ident))


class Revoke(Base):
    def __init__(self, device_id: str) -> None:
        super().__init__()
        self.device_id = device_id

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Revoke device", classes="heading")
        yield Static(f"Revoke {self.device_id}? This invalidates its credential immediately.")
        with Horizontal():
            yield Button("Cancel", id="cancel")
            yield Button("Revoke device", id="confirm", variant="error")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            result = await operations.revoke(self.device_id)
            self.app.notify(
                result, severity="error" if operations.revoke_failed(result) else "information"
            )
        self.app.switch_screen(Devices())


class Approvals(Base):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Pending approvals", classes="heading")
        yield Static("", id="approval-status")
        yield DataTable(id="table")
        yield Input(placeholder="Invocation ID", id="invocation")
        yield Select(
            [
                ("One time", "one_time"),
                ("Session", "session"),
                ("Device", "device"),
                ("Persistent", "persistent"),
            ],
            value="one_time",
            id="scope",
        )
        with Horizontal():
            yield Button("Approve", id="approve", variant="success")
            yield Button("Deny", id="deny", variant="error")
            yield Button("Refresh", id="refresh")
            yield Button("Menu", id="menu")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#table", DataTable).add_columns(
            "ID", "Device", "Capability", "Risk", "Expires"
        )
        await self.load_approvals()

    async def load_approvals(self) -> None:
        payload, error = await self.request("ctl_list_approvals", {})
        table = self.query_one("#table", DataTable)
        table.clear()
        if not payload:
            self.query_one("#approval-status", Static).update(f"Offline — {error}")
            return
        rows = payload.get("approvals", [])
        self.query_one("#approval-status", Static).update(f"{len(rows)} pending")
        for x in rows:
            table.add_row(
                str(x.get("invocation_id")),
                str(x.get("device_id")),
                str(x.get("capability")),
                str(x.get("risk_class")),
                _when(x.get("expires_at")),
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "menu":
            self.menu()
        elif action == "refresh":
            await self.load_approvals()
        elif action in {"approve", "deny"}:
            ident = self.query_one("#invocation", Input).value.strip()
            scope = self.query_one("#scope", Select).value
            if ident and isinstance(scope, str):
                _, error = await self.request(
                    "ctl_resolve_approval",
                    {"invocation_id": ident, "decision": action, "scope": scope},
                )
                self.app.notify(
                    error or f"Approval {action}d", severity="error" if error else "information"
                )
                await self.load_approvals()


class Audit(Base):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Today's audit log", classes="heading")
        yield Static("Loading…", id="content")
        yield Button("Menu", id="menu")
        yield Footer()

    async def on_mount(self) -> None:
        payload, error = await self.request("ctl_audit_tail", {})
        content = (
            "\n".join(json.dumps(x, sort_keys=True) for x in payload.get("lines", []))
            if payload
            else f"Offline — {error}"
        )
        self.query_one("#content", Static).update(content or "No records today.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.menu()


class Policy(Base):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Policy", classes="heading")
        yield Static("Loading…", id="content")
        yield Input(placeholder="Optional policy file to validate", id="path")
        with Horizontal():
            yield Button("Reload", id="reload")
            yield Button("Validate", id="validate")
            yield Button("Menu", id="menu")
        yield Footer()

    async def on_mount(self) -> None:
        await self.show()

    async def show(self) -> None:
        payload, error = await self.request("ctl_policy_show", {})
        self.query_one("#content", Static).update(
            json.dumps(payload, indent=2, sort_keys=True) if payload else f"Offline — {error}"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "menu":
            self.menu()
        elif event.button.id == "reload":
            payload, error = await self.request("ctl_policy_reload", {})
            self.app.notify(
                error or json.dumps(payload, sort_keys=True),
                severity="error" if error else "information",
            )
            await self.show()
        elif event.button.id == "validate":
            path = Path(self.query_one("#path", Input).value.strip() or config.policy_path())
            ok = PolicyEngine(
                path, known_device_ids=Registry(config.registry_db_path()).known_active_device_ids
            ).reload(force=True)
            self.app.notify(
                f"{'Valid' if ok else 'Invalid'} policy: {path}",
                severity="information" if ok else "error",
            )


class HDPApp(App[None]):
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    CSS = """
    Screen { align: center top; padding: 1 3; }
    #title { text-align: center; text-style: bold; color: $accent; margin: 2 0 1 0; }
    #profile, .hint { color: $text-muted; text-align: center; margin-bottom: 1; }
    #menu { width: 48; height: auto; }
    #menu Button { width: 100%; margin-bottom: 1; }
    Button:focus { text-style: bold; }
    .heading { text-style: bold; color: $accent; margin: 1 0; }
    #pair-status, #pair-detail { width: 100%; text-align: center; }
    DataTable { height: 1fr; width: 100%; }
    Input, Select { width: 100%; margin: 1 0; }
    Horizontal { height: auto; margin: 1 0; }
    Horizontal Button { margin-right: 1; }
    #content { height: 1fr; width: 100%; overflow: auto; }
    """
    TITLE = "HDP"

    def on_mount(self) -> None:
        self.push_screen(Menu())
