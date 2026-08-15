"""Profile-scoped paths, timeouts, and defaults for the standalone `hdp-bridge` daemon.

ADR-0006's rule, restated as code: **nothing here is cached at import time.** Every accessor
reads `$HERMES_HOME` fresh on every call. A module-level `HDP_HOME = Path(os.environ[...]) / "hdp"`
is the single easiest way to make two Hermes profiles silently share one device registry, one
policy store, and one audit log — and the failure is silent, which is what makes it dangerous. A
device paired under a personal profile must never be reachable from a work profile.

This is a near-verbatim copy of `hermes_device_plugin/config.py`'s path/bind accessors, kept as a
separate module rather than a shared import per the plan's Global Constraints (`hdp_bridge` must
never import from `hermes_device_plugin`). It adds the two paths specific to the daemon side of
the control socket: `control_socket_path()` and `pid_path()`.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HDP_BIND_HOST = "127.0.0.1"
DEFAULT_HDP_BIND_PORT = 8765


def hermes_home() -> Path:
    """The active Hermes profile's state root. Read fresh on every call — never cache this."""
    return Path(os.environ["HERMES_HOME"]).expanduser()


def hdp_home() -> Path:
    """`$HERMES_HOME/hdp/` — where all HDP state lives, profile-scoped (FR-17, ADR-0006)."""
    return hermes_home() / "hdp"


def hdp_bind_host() -> str:
    """The host the aiohttp node-facing server binds to. Read fresh on every call (ADR-0006) —
    a module-level constant here would survive a profile switch within one process. Binding to
    anything other than loopback requires `HDP_ALLOW_REMOTE=1` (NFR-4) — enforced by the server,
    not by this accessor, which just reports the configured value."""
    return os.environ.get("HDP_BIND_HOST", DEFAULT_HDP_BIND_HOST)


def hdp_bind_port() -> int:
    """The port the aiohttp node-facing server binds to. `0` (test convention) requests an
    OS-assigned ephemeral port. Read fresh on every call (ADR-0006)."""
    return int(os.environ.get("HDP_BIND_PORT", DEFAULT_HDP_BIND_PORT))


def hdp_allow_remote() -> bool:
    """NFR-4's guard: binding to a non-loopback host is refused unless this is set."""
    return os.environ.get("HDP_ALLOW_REMOTE") == "1"


def bridge_addr_path() -> Path:
    """`$HERMES_HOME/hdp/bridge.addr` — a plaintext `host:port` file the running server writes on
    start and removes on close, so `hdp-node connect` can discover the bound address without a
    hardcoded port. Read fresh on every call, same discipline as every other accessor here."""
    return hdp_home() / "bridge.addr"


def control_socket_path() -> Path:
    """`$HERMES_HOME/hdp/bridge.sock` — the plugin↔bridge Unix control socket, mode 0600
    (ADR-0006, trust boundary 2)."""
    return hdp_home() / "bridge.sock"


def pid_path() -> Path:
    """`$HERMES_HOME/hdp/bridge.pid`, written by `daemon.py` after the control socket is bound."""
    return hdp_home() / "bridge.pid"


def registry_db_path() -> Path:
    return hdp_home() / "registry.db"
