from __future__ import annotations

import asyncio

from hdp_bridge.pairing import consume_pairing_code, mint_pairing_code
from hdp_bridge.store import db


def test_minted_code_is_grouped_base32_and_not_the_stored_hash(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    assert "-" in code  # grouped for human legibility
    stored = conn.execute("SELECT code_hash FROM pairing_codes").fetchone()[0]
    assert code not in stored  # never the plaintext, hashed only (no-plaintext rule)


def test_consume_succeeds_exactly_once(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    assert consume_pairing_code(conn, code, "dev_1") is True
    assert consume_pairing_code(conn, code, "dev_2") is False  # already consumed


def test_consume_fails_after_ttl_expires(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn, now_ms=0)
    assert consume_pairing_code(conn, code, "dev_1", now_ms=6 * 60 * 1000) is False  # 6 min later


def test_unknown_code_fails_without_distinguishing_why(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    assert consume_pairing_code(conn, "NOPE-NOPE-NOPE", "dev_1") is False


async def test_concurrent_consumption_has_exactly_one_winner(tmp_path):
    """FR-11's core claim: two nodes racing one code, exactly one gets a device_id."""
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)

    def try_consume(device_id: str) -> bool:
        # Separate connection per "node", same file — exercises the real WAL/busy_timeout path,
        # not just Python-level concurrency against one connection.
        local_conn = db.connect(tmp_path / "registry.db")
        try:
            return consume_pairing_code(local_conn, code, device_id)
        finally:
            local_conn.close()

    results = await asyncio.gather(
        asyncio.to_thread(try_consume, "dev_a"), asyncio.to_thread(try_consume, "dev_b")
    )
    assert sorted(results) == [False, True]
