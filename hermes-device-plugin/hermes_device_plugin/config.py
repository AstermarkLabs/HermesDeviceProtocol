"""Profile-scoped paths, timeouts, and defaults.

ADR-0006's rule, restated as code: **nothing here is cached at import time.** Every accessor
reads `$HERMES_HOME` fresh on every call. A module-level `HDP_HOME = Path(os.environ[...]) / "hdp"`
is the single easiest way to make two Hermes profiles silently share one device registry, one
policy store, and one audit log — and the failure is silent, which is what makes it dangerous. A
device paired under a personal profile must never be reachable from a work profile.

At M1 the only thing behind these paths is `bridge.addr`, the server's discovery file (no SQLite,
no policy file, no audit log — all M2/M3). The rest of the accessors exist now so nothing
downstream has to retrofit "read at use time" later.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_INVOCATION_DEADLINE_MS = 30_000
"""Default deadline for a device invocation. `engine.py` carries it into every `InvokeRequest`,
and from M1 it is really enforced: `EmbeddedTransport.invoke` waits on the result future for
exactly this long before returning `invocation_timeout`."""

APPROVAL_EXPIRY_SECONDS = 120
"""Default `pending_approval` TTL (seed §17). Unused until M3; declared here so the constant has
one home instead of being invented at the M3 call site."""

ACK_TIMEOUT_S = 5.0
"""Ack timeout for an invocation, strictly less than any device's execution deadline
(hdp-spec/HDP-0.md §7). A node that never acks fails fast (`device_offline`) instead of burning
the full deadline."""

DEFAULT_HDP_BIND_HOST = "127.0.0.1"
DEFAULT_HDP_BIND_PORT = 8765


def hermes_home() -> Path:
    """The active Hermes profile's state root. Read fresh on every call — never cache this."""
    return Path(os.environ["HERMES_HOME"]).expanduser()


def hdp_home() -> Path:
    """`$HERMES_HOME/hdp/` — where all HDP state lives, profile-scoped (FR-17, ADR-0006)."""
    return hermes_home() / "hdp"


def hdp_bind_host() -> str:
    """The host the M1 embedded server binds to. Read fresh on every call (ADR-0006) — a
    module-level constant here would survive a profile switch within one process. Binding to
    anything other than loopback requires `HDP_ALLOW_REMOTE=1` (NFR-4) — enforced by the server,
    not by this accessor, which just reports the configured value."""
    return os.environ.get("HDP_BIND_HOST", DEFAULT_HDP_BIND_HOST)


def hdp_bind_port() -> int:
    """The port the M1 embedded server binds to. `0` (test convention) requests an OS-assigned
    ephemeral port. Read fresh on every call (ADR-0006)."""
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
    """`$HERMES_HOME/hdp/bridge.sock` — the M2 plugin↔bridge Unix control socket. A near-verbatim
    duplicate of `hdp_bridge.config.control_socket_path()`: both packages independently know
    where this path lives, same as both already independently know `bridge.addr`'s path
    (`hdp_bridge` must never be imported from here, per this plan's Global Constraints)."""
    return hdp_home() / "bridge.sock"
