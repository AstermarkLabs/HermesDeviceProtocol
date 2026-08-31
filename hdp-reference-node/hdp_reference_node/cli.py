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
    credentials = connect.add_mutually_exclusive_group()
    credentials.add_argument(
        "--credential",
        default=None,
        help=(
            "Existing device credential to use for this process only. When provided, the "
            "credential file is neither read nor written, allowing multiple nodes to run "
            "without changing the stored default credential."
        ),
    )
    credentials.add_argument(
        "--enrollment-id",
        default=None,
        help="Opaque identifier received through the physical USB bootstrap.",
    )
    connect.add_argument(
        "--credential-file",
        default="./.hdp-node-credential",
        dest="credential_file",
        help=(
            "Path this reference node reads its stored device credential from, and writes the "
            "bridge-issued credential to on a successful first-time pairing (M2). Defaults to "
            "./.hdp-node-credential for the reference implementation's convenience."
        ),
    )
    connect.add_argument("--device-key-file", default="./.hdp-node-key.pem")
    connect.add_argument(
        "--capability-version",
        action="append",
        default=[],
        dest="capability_versions",
        metavar="NAME@N",
        help=(
            "Conformance-only advertised capability version override, repeatable. Overrides "
            "replace the built-in version set for each named capability."
        ),
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
        try:
            descriptors = node.descriptors_for_overrides(args.capability_versions)
        except ValueError as exc:
            parser.error(str(exc))
        try:
            asyncio.run(
                node.run(
                    url,
                    args.name,
                    faults,
                    enrollment_id=args.enrollment_id,
                    credential=args.credential,
                    credential_file=Path(args.credential_file),
                    device_key_file=Path(args.device_key_file),
                    descriptors=descriptors,
                )
            )
        except node.AuthFailed as exc:
            # A terminal, operator-actionable condition — a one-line diagnosis and a nonzero
            # exit, not a traceback.
            if args.credential is not None:
                remediation = (
                    "Verify the process-only `--credential` value or enroll this node again; "
                    "the shared credential file was not used or changed."
                )
            else:
                remediation = (
                    "Connect the device by USB and run local bootstrap, "
                    f"after removing {args.credential_file}."
                )
            raise SystemExit(f"{exc}. {remediation}") from exc
