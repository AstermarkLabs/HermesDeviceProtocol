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

    args = parser.parse_args()
    if args.command == "serve":
        daemon.main()
    elif args.command == "pair" and args.pair_command == "new":
        from . import config
        from .pairing import mint_pairing_code
        from .store import db as store_db

        conn = store_db.connect(config.registry_db_path())
        code = mint_pairing_code(conn)
        print(code)
    elif args.command == "devices" and args.devices_command == "revoke":
        _run_devices_revoke(args.device_id)


def _run_devices_revoke(device_id: str) -> None:
    """Tries the control socket first (reaches a live connection so the `revoke` frame and socket
    close actually happen, not just the DB-side credential invalidation); falls back to a direct
    DB-only revoke if no daemon is reachable — there's nothing live to disconnect in that case
    anyway, and the credential must still be invalidated so a later daemon start doesn't let the
    device back in."""
    import asyncio

    async def _via_control_socket() -> bool:
        from hdp_proto.envelope import Envelope

        from .config import control_socket_path
        from .control import read_frame, write_frame

        try:
            reader, writer = await asyncio.open_unix_connection(str(control_socket_path()))
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            return False
        await write_frame(
            writer, Envelope.new("ctl_devices_revoke", {"device_id": device_id}).to_wire()
        )
        await read_frame(reader)
        writer.close()
        return True

    reached_daemon = asyncio.run(_via_control_socket())
    if not reached_daemon:
        from . import config, credentials
        from .store import db as store_db

        conn = store_db.connect(config.registry_db_path())
        credentials.revoke_credential(conn, device_id)
    print(f"revoked {device_id}")
