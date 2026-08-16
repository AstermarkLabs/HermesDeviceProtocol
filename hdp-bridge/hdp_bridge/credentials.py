"""Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time


def _hash(credential: str) -> str:
    return hashlib.sha256(credential.encode("ascii")).hexdigest()


def issue_credential(conn: sqlite3.Connection, device_id: str) -> str:
    """Returns the credential in plaintext. The caller (the `hello` handler, or `pair --new`'s
    completion) is responsible for sending it exactly once and never logging it (no-plaintext
    rule)."""
    credential = os.urandom(32).hex()  # 256 bits
    with conn:
        conn.execute(
            "INSERT INTO credentials (device_id, credential_hash, issued_at, revoked_at) "
            "VALUES (?, ?, ?, NULL)",
            (device_id, _hash(credential), int(time.time() * 1000)),
        )
    return credential


def verify_credential(conn: sqlite3.Connection, device_id: str, presented: str) -> bool:
    row = conn.execute(
        "SELECT credential_hash FROM credentials WHERE device_id = ? AND revoked_at IS NULL "
        "ORDER BY issued_at DESC LIMIT 1",
        (device_id,),
    ).fetchone()
    if row is None:
        return False
    return hmac.compare_digest(row[0], _hash(presented))


def verify_credential_and_resolve_device(conn: sqlite3.Connection, presented: str) -> str | None:
    """Returns the device_id the credential belongs to, or None if it matches no live credential.
    Necessary because `hello` identifies a returning device *by its credential*, not by a
    device_id the node doesn't have (M2 wire-shape decision — hdp_proto.messages.Hello is
    unchanged, no new field added, per D1's 'no wire break' promise).

    Linear scan is correct at MVP scale — a handful of paired devices per profile, not a
    performance-sensitive path.
    """
    rows = conn.execute(
        "SELECT device_id, credential_hash FROM credentials WHERE revoked_at IS NULL"
    ).fetchall()
    for device_id, stored_hash in rows:
        if hmac.compare_digest(stored_hash, _hash(presented)):
            return device_id
    return None


def revoke_credential(conn: sqlite3.Connection, device_id: str) -> None:
    with conn:
        conn.execute(
            "UPDATE credentials SET revoked_at = ? WHERE device_id = ? AND revoked_at IS NULL",
            (int(time.time() * 1000), device_id),
        )
        conn.execute("UPDATE devices SET state = 'revoked' WHERE device_id = ?", (device_id,))
