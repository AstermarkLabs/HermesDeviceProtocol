"""Pairing-code minting, the online-guessing budget, and atomic consumption (FR-11, §4.1).

Minting is operator-only, structurally — the only caller in this repo is `hdp-bridge pair --new`
(§4.2); there is no control-plane verb for it (`ctl_pair_mint` is always rejected, see control.py).

**Why a six-digit code is safe here (HDP-0.md Amendments v0.4).** The code carries ~20 bits, not
the 128 it used to. Entropy alone would not survive an online guesser. What bounds the attack is
`burn_attempt`: every failed pairing handshake decrements the budget of *every* live code, and a
code whose budget reaches zero is permanently invalidated rather than merely rate-limited. A
guesser therefore gets `_ATTEMPT_BUDGET` tries against a 1,000,000-code space per pairing window
(~5e-6), which is far stronger than the raw entropy suggests.

The decrement deliberately applies to all live codes rather than only a code that matched, because
a guesser's wrong codes match no row at all — a per-code-only counter would bound nothing.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Literal

_TTL_MS = 5 * 60 * 1000
_CODE_DIGITS = 6

#: Failed attempts a live code tolerates before it is destroyed. Small on purpose: a human
#: mistypes a six-digit code once or twice, never five times.
_ATTEMPT_BUDGET = 5

#: Resamples allowed before minting gives up (see `mint_pairing_code`).
_MINT_ATTEMPTS = 20


def _random_code() -> str:
    """Uniform over the full six-digit space, leading zeros included — `secrets.randbelow` avoids
    the modulo bias a `randint`-over-`urandom` construction would introduce."""
    return f"{secrets.randbelow(10**_CODE_DIGITS):0{_CODE_DIGITS}d}"


def _hash_code(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


class NoPairingCodeAvailableError(RuntimeError):
    """Every sampled code collided with a code that is still live. Only reachable with an absurd
    number of concurrent outstanding pairings; surfaces as an operator error rather than handing
    back a code that is not actually the caller's."""


@dataclass(frozen=True)
class PairingStatus:
    """Read-only lifecycle state for an operator-owned pairing code."""

    state: Literal["pending", "consumed", "expired", "invalidated", "unknown"]
    issued_device_id: str | None
    expires_at: int | None


def mint_pairing_code(conn: sqlite3.Connection, *, now_ms: int | None = None) -> str:
    """Mint a fresh six-digit code.

    `code_hash` is the primary key, so a hash that is already present cannot simply be inserted.
    With 128-bit codes that was unreachable; across a 1,000,000-code space it is routine, and the
    rows of long-dead codes would otherwise permanently consume the space. So: a colliding row
    that is *dead* (consumed, expired, or invalidated) is replaced, and a collision with a *live*
    code is retried with a fresh sample.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    for _ in range(_MINT_ATTEMPTS):
        code = _random_code()
        code_hash = _hash_code(code)
        with conn:
            existing = conn.execute(
                "SELECT consumed_at, invalidated_at, expires_at FROM pairing_codes "
                "WHERE code_hash = ?",
                (code_hash,),
            ).fetchone()
            if existing is not None:
                still_live = existing[0] is None and existing[1] is None and existing[2] > now_ms
                if still_live:
                    continue
                conn.execute("DELETE FROM pairing_codes WHERE code_hash = ?", (code_hash,))
            conn.execute(
                "INSERT INTO pairing_codes (code_hash, created_at, expires_at, consumed_at, "
                "issued_device_id, attempts_remaining) VALUES (?, ?, ?, NULL, NULL, ?)",
                (code_hash, now_ms, now_ms + _TTL_MS, _ATTEMPT_BUDGET),
            )
            return code
    raise NoPairingCodeAvailableError(
        f"could not find a free pairing code in {_MINT_ATTEMPTS} attempts"
    )


def code_is_live(conn: sqlite3.Connection, code: str, *, now_ms: int | None = None) -> bool:
    """Does this code currently match an unconsumed, unexpired, uninvalidated row?

    Used by the v0.4 handshake to decide whether to issue a challenge, *without* consuming the
    code — consumption must not happen until the node has proven possession of its private key,
    or a guesser who hit the right code could burn it without completing the exchange.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    row = conn.execute(
        "SELECT 1 FROM pairing_codes WHERE code_hash = ? AND consumed_at IS NULL "
        "AND invalidated_at IS NULL AND expires_at > ?",
        (_hash_code(code), now_ms),
    ).fetchone()
    return row is not None


def pairing_status(
    conn: sqlite3.Connection, code: str, *, now_ms: int | None = None
) -> PairingStatus:
    """Return a code's lifecycle state without exposing its stored hash."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    row = conn.execute(
        "SELECT expires_at, consumed_at, invalidated_at, issued_device_id FROM pairing_codes "
        "WHERE code_hash = ?",
        (_hash_code(code),),
    ).fetchone()
    if row is None:
        return PairingStatus("unknown", None, None)
    expires_at, consumed_at, invalidated_at, issued_device_id = row
    if consumed_at is not None:
        return PairingStatus("consumed", issued_device_id, expires_at)
    if invalidated_at is not None:
        return PairingStatus("invalidated", None, expires_at)
    if expires_at <= now_ms:
        return PairingStatus("expired", None, expires_at)
    return PairingStatus("pending", None, expires_at)


def burn_attempt(conn: sqlite3.Connection, *, now_ms: int | None = None) -> int:
    """Charge one failed pairing attempt against every live code, destroying any that run out.

    Returns the number of codes invalidated by this call, for audit. Called on *every* failed
    pairing handshake — wrong code, failed proof, or malformed exchange alike.

    Accepted trade-off: anyone who can reach the bridge can burn an operator's pairing window
    this way. That is fail-closed by design; the window is already five minutes and re-minting is
    a single command. Trading a denial-of-pairing for an open brute-force channel would be the
    worse bargain.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    with conn:
        conn.execute(
            "UPDATE pairing_codes SET attempts_remaining = attempts_remaining - 1 "
            "WHERE consumed_at IS NULL AND invalidated_at IS NULL AND expires_at > ?",
            (now_ms,),
        )
        cursor = conn.execute(
            "UPDATE pairing_codes SET invalidated_at = ? "
            "WHERE consumed_at IS NULL AND invalidated_at IS NULL AND attempts_remaining <= 0",
            (now_ms,),
        )
        return cursor.rowcount


def consume_pairing_code(
    conn: sqlite3.Connection, code: str, device_id: str, *, now_ms: int | None = None
) -> bool:
    """The single atomic statement FR-11 requires — see docs/m2-plan.md §4.1 for why a
    SELECT-then-UPDATE is not an acceptable alternative implementation."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    with conn:
        cursor = conn.execute(
            "UPDATE pairing_codes SET consumed_at = ?, issued_device_id = ? "
            "WHERE code_hash = ? AND consumed_at IS NULL AND invalidated_at IS NULL "
            "AND expires_at > ?",
            (now_ms, device_id, _hash_code(code), now_ms),
        )
        return cursor.rowcount == 1
