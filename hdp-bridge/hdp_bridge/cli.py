"""`hdp-bridge` CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hdp_proto.envelope import Envelope

from . import daemon


def main() -> None:
    if len(sys.argv) == 1:
        _run_tui()
        return

    parser = argparse.ArgumentParser(prog="hdp")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("serve", help="Run the HDP bridge daemon in the foreground.")

    pair = subparsers.add_parser("pair", help="Pairing operations.")
    pair_sub = pair.add_subparsers(dest="pair_command", required=True)
    pair_sub.add_parser("new", help="Deprecated: pairing codes are disabled.")
    usb_pair = pair_sub.add_parser("usb", help="Bootstrap a USB-connected Android accessory.")
    usb_pair.add_argument(
        "--serial", default="", help="Android USB serial; use with multiple devices."
    )

    devices = subparsers.add_parser("devices", help="Device operations.")
    devices_sub = devices.add_subparsers(dest="devices_command", required=True)
    devices_sub.add_parser("list", help="List successfully paired devices.")
    revoke_parser = devices_sub.add_parser("revoke", help="Revoke a paired device immediately.")
    revoke_parser.add_argument("device_id")
    remove_parser = devices_sub.add_parser("remove", help="Remove a paired device immediately.")
    remove_parser.add_argument("device_id")

    audit_parser = subparsers.add_parser("audit", help="Audit log operations.")
    audit_sub = audit_parser.add_subparsers(dest="audit_command", required=True)
    audit_sub.add_parser("tail", help="Print today's audit records.")

    approvals = subparsers.add_parser("approvals", help="Pending approval operations.")
    approvals_sub = approvals.add_subparsers(dest="approvals_command", required=True)
    approvals_sub.add_parser("list", help="List daemon-held pending approvals.")
    for decision in ("approve", "deny"):
        decision_parser = approvals_sub.add_parser(
            decision, help=f"{decision.title()} a pending invocation."
        )
        decision_parser.add_argument("invocation_id")
        decision_parser.add_argument(
            "--scope",
            choices=("one_time", "session", "device", "persistent"),
            default="one_time",
        )

    policy = subparsers.add_parser("policy", help="Read-only policy operations.")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("show", aliases=["status"], help="Show the effective daemon policy.")
    validate = policy_sub.add_parser("validate", help="Validate a policy file without applying it.")
    validate.add_argument("path", nargs="?", type=Path)
    policy_sub.add_parser("reload", help="Force the daemon to reload policy.yaml.")

    args = parser.parse_args()
    if args.command == "serve":
        daemon.main()
    elif args.command == "pair" and args.pair_command == "new":
        _run_pair_new()
    elif args.command == "pair" and args.pair_command == "usb":
        _run_usb_pair(args.serial)
    elif args.command == "devices" and args.devices_command == "list":
        _run_devices_list()
    elif args.command == "devices" and args.devices_command in {"revoke", "remove"}:
        _run_devices_revoke(args.device_id)
    elif args.command == "audit" and args.audit_command == "tail":
        _run_audit_tail()
    elif args.command == "approvals" and args.approvals_command == "list":
        _run_approvals_list()
    elif args.command == "approvals":
        _run_approval_resolve(
            args.invocation_id,
            decision=args.approvals_command,
            scope=args.scope,
        )
    elif args.command == "policy" and args.policy_command in {"show", "status", "reload"}:
        _run_policy_control(args.policy_command)
    elif args.command == "policy" and args.policy_command == "validate":
        _run_policy_validate(args.path)


def _run_pair_new() -> None:
    import asyncio

    from . import operations

    try:
        print(asyncio.run(operations.pair_new()))
    except operations.PairingCodeRemovedError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def _run_usb_pair(serial: str) -> None:
    reply = _control_request("ctl_usb_bootstrap", {"serial": serial})
    if reply.type != "ctl_usb_bootstrap_reply":
        print(reply.payload.get("message", "USB bootstrap was refused"), file=sys.stderr)
        raise SystemExit(2)
    print("USB bootstrap approved; complete the device network enrollment now.")


def _run_tui() -> None:
    from .tui import HDPApp

    HDPApp().run()


def _run_audit_tail() -> None:
    import time

    from . import config

    day = time.strftime("%Y-%m-%d", time.gmtime())
    path = config.hdp_home() / "audit" / f"audit-{day}.jsonl"
    if path.exists():
        print(path.read_text(), end="")


def _run_devices_revoke(device_id: str) -> None:
    """Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback decision,
    the audit record, and the did-anything-actually-happen check all live there, shared with
    `hermes hdp devices revoke` (final-review finding I5). Exits non-zero on a refused/no-op
    revoke rather than always exiting 0 (re-review finding I4, round 2) — a script that does
    `hdp devices revoke $id && next-step` must not proceed past a revoke that did nothing.
    """
    import asyncio

    from . import operations

    message = asyncio.run(operations.revoke(device_id))
    print(message)
    if operations.revoke_failed(message):
        raise SystemExit(1)


def _run_devices_list() -> None:
    reply = _control_request("ctl_list_devices", {})
    devices = reply.payload.get("devices", [])
    if not devices:
        print("No paired devices.")
        return

    headers = ("NAME", "PLATFORM", "DEVICE ID", "STATE", "ONLINE", "CAPS")
    rows = [
        (
            str(device.get("friendly_name", "")),
            str(device.get("platform", "")),
            str(device.get("device_id", "")),
            str(device.get("state", "active")),
            "online" if device.get("online") else "offline",
            str(len(device.get("capabilities", []))),
        )
        for device in devices
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)
    ]

    def render(row: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip()

    print(render(headers))
    print(render(tuple("-" * width for width in widths)))
    for row in rows:
        print(render(row))


def _run_approvals_list() -> None:
    reply = _control_request("ctl_list_approvals", {})
    print(json.dumps(reply.payload.get("approvals", []), sort_keys=True))


def _run_approval_resolve(invocation_id: str, *, decision: str, scope: str) -> None:
    reply = _control_request(
        "ctl_resolve_approval",
        {"invocation_id": invocation_id, "decision": decision, "scope": scope},
    )
    print(json.dumps(reply.payload, sort_keys=True))


def _run_policy_control(command: str) -> None:
    verb = "ctl_policy_reload" if command == "reload" else "ctl_policy_show"
    reply = _control_request(verb, {})
    print(json.dumps(reply.payload, sort_keys=True))


def _run_policy_validate(path: Path | None) -> None:
    from . import config
    from .policy import PolicyEngine
    from .registry import Registry

    registry = Registry(config.registry_db_path())
    engine = PolicyEngine(
        path or config.policy_path(), known_device_ids=registry.known_active_device_ids
    )
    accepted = engine.reload(force=True)
    result = {"ok": accepted, "policy_seq": engine.table.policy_seq}
    print(json.dumps(result, sort_keys=True))
    if not accepted:
        raise SystemExit(1)


def _control_request(verb: str, payload: dict) -> Envelope:
    import asyncio

    from . import operations

    reply = asyncio.run(operations.control_request(verb, payload))
    if reply.type == "error":
        print(json.dumps({"ok": False, "error": reply.payload}, sort_keys=True))
        raise SystemExit(1)
    return reply
