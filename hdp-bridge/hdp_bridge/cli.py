"""`hdp-bridge` CLI."""

from __future__ import annotations

import argparse

from . import daemon


def main() -> None:
    parser = argparse.ArgumentParser(prog="hdp-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("serve", help="Run the HDP bridge daemon in the foreground.")
    args = parser.parse_args()
    if args.command == "serve":
        daemon.main()
