"""Profile-scoped paths, timeouts, and defaults.

ADR-0006's rule, restated as code: **nothing here is cached at import time.** Every accessor
reads `$HERMES_HOME` fresh on every call. A module-level `HDP_HOME = Path(os.environ[...]) / "hdp"`
is the single easiest way to make two Hermes profiles silently share one device registry, one
policy store, and one audit log — and the failure is silent, which is what makes it dangerous. A
device paired under a personal profile must never be reachable from a work profile.

At M0 nothing is behind these paths yet (no SQLite, no policy file, no audit log — all M2/M3).
The functions exist now so nothing downstream has to retrofit "read at use time" later.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_INVOCATION_DEADLINE_MS = 30_000
"""Default deadline for a device invocation. Not yet enforced against a real transport at M0 —
the loopback stub returns synchronously — but the default lives here so `engine.py` has a real
value to carry from day one rather than a magic number at the call site."""

APPROVAL_EXPIRY_SECONDS = 120
"""Default `pending_approval` TTL (seed §17). Unused until M3; declared here so the constant has
one home instead of being invented at the M3 call site."""


def hermes_home() -> Path:
    """The active Hermes profile's state root. Read fresh on every call — never cache this."""
    return Path(os.environ["HERMES_HOME"]).expanduser()


def hdp_home() -> Path:
    """`$HERMES_HOME/hdp/` — where all HDP state lives, profile-scoped (FR-17, ADR-0006)."""
    return hermes_home() / "hdp"
