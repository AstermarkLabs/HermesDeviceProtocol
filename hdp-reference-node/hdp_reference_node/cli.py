"""`hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect --name
workshop-node`).

Deliberately does not import `hermes_device_plugin` — the node is a separate process (and, from
M2 on, potentially a separate machine) representing a different device; depending on the Hermes
plugin package here would be backwards. `--url`'s default is discovered by reading
`$HERMES_HOME/hdp/bridge.addr` directly (duplicating the few lines that read that file, not the
package that writes it).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from . import node
from .faults import FaultConfig


def _default_bridge_url() -> str:
    hermes_home = os.environ.get("HERMES_HOME")
    if not hermes_home:
        raise SystemExit(
            "--url was not given and $HERMES_HOME is not set; cannot discover the bridge"
        )
    addr_path = Path(hermes_home).expanduser() / "hdp" / "bridge.addr"
    if not addr_path.exists():
        raise SystemExit(
            f"--url was not given and {addr_path} does not exist — is the bridge running?"
        )
    host_port = addr_path.read_text().strip()
    return f"ws://{host_port}/hdp/v0/socket"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hdp-node")
    subparsers = parser.add_subparsers(dest="command", required=True)

    connect = subparsers.add_parser(
        "connect", help="Connect to an HDP bridge and serve capabilities."
    )
    connect.add_argument("--name", required=True, help="Device name to advertise.")
    connect.add_argument(
        "--url",
        default=None,
        help="Bridge WebSocket URL. Defaults to discovering $HERMES_HOME/hdp/bridge.addr.",
    )
    connect.add_argument(
        "--fault",
        action="append",
        default=[],
        dest="faults",
        help="Fault-injection flag, repeatable (see hdp_reference_node.faults.FaultConfig).",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "connect":
        url = args.url or _default_bridge_url()
        faults = FaultConfig.parse(args.faults)
        asyncio.run(node.run(url, args.name, faults))
