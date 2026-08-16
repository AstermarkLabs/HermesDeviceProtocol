"""Pairing-code minting and atomic consumption (FR-11, §4.1). Minting is operator-only,
structurally — the only caller in this repo is `hdp-bridge pair --new` (§4.2); there is no
control-plane verb for it (`ctl_pair_mint` is always rejected, see control.py)."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time

_TTL_MS = 5 * 60 * 1000
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _random_code() -> str:
    raw = os.urandom(16)  # 128 bits
    value = int.from_bytes(raw, "big")
    chars = []
    for _ in range(26):  # 128 bits / 5 bits-per-char, rounded up
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    chars.reverse()
    grouped = "-".join("".join(chars[i:i + 4]) for i in range(0, len(chars), 4))
    return grouped


def _hash_code(code: str) -> str:
    normalized = code.replace("-", "").upper()
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


def mint_pairing_code(conn: sqlite3.Connection, *, now_ms: int | None = None) -> str:
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    code = _random_code()
    with conn:
        conn.execute(
            "INSERT INTO pairing_codes (code_hash, created_at, expires_at, consumed_at, "
            "issued_device_id) VALUES (?, ?, ?, NULL, NULL)",
            (_hash_code(code), now_ms, now_ms + _TTL_MS),
        )
    return code


def consume_pairing_code(
    conn: sqlite3.Connection, code: str, device_id: str, *, now_ms: int | None = None
) -> bool:
    """The single atomic statement FR-11 requires — see docs/m2-plan.md §4.1 for why a
    SELECT-then-UPDATE is not an acceptable alternative implementation."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    with conn:
        cursor = conn.execute(
            "UPDATE pairing_codes SET consumed_at = ?, issued_device_id = ? "
            "WHERE code_hash = ? AND consumed_at IS NULL AND expires_at > ?",
            (now_ms, device_id, _hash_code(code), now_ms),
        )
        return cursor.rowcount == 1
