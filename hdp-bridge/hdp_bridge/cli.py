"""`hdp-bridge` CLI."""

from __future__ import annotations

import argparse

from . import daemon


def main() -> None:
    parser = argparse.ArgumentParser(prog="hdp-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("serve", help="Run the HDP bridge daemon in the foreground.")

    pair = subparsers.add_parser("pair", help="Pairing operations.")
    pair_sub = pair.add_subparsers(dest="pair_command", required=True)
    pair_sub.add_parser("new", help="Mint a new pairing code.")

    devices = subparsers.add_parser("devices", help="Device operations.")
    devices_sub = devices.add_subparsers(dest="devices_command", required=True)
    revoke_parser = devices_sub.add_parser("revoke", help="Revoke a paired device immediately.")
    revoke_parser.add_argument("device_id")

    audit_parser = subparsers.add_parser("audit", help="Audit log operations.")
    audit_sub = audit_parser.add_subparsers(dest="audit_command", required=True)
    audit_sub.add_parser("tail", help="Print today's audit records.")

    args = parser.parse_args()
    if args.command == "serve":
        daemon.main()
    elif args.command == "pair" and args.pair_command == "new":
        _run_pair_new()
    elif args.command == "devices" and args.devices_command == "revoke":
        _run_devices_revoke(args.device_id)
    elif args.command == "audit" and args.audit_command == "tail":
        _run_audit_tail()


def _run_pair_new() -> None:
    import asyncio

    from . import operations

    print(asyncio.run(operations.pair_new()))


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
    `hermes hdp devices revoke` (final-review finding I5)."""
    import asyncio

    from . import operations

    print(asyncio.run(operations.revoke(device_id)))
