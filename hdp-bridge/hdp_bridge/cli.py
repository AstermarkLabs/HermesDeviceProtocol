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
