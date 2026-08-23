from __future__ import annotations

import asyncio

import pytest
from hdp_bridge import pairing
from hdp_bridge.pairing import (
    burn_attempt,
    code_is_live,
    consume_pairing_code,
    mint_pairing_code,
)
from hdp_bridge.store import db


def test_minted_code_is_six_digits_and_not_the_stored_hash(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    assert len(code) == 6
    assert code.isdigit()  # typable on a numeric keypad (v0.4)
    stored = conn.execute("SELECT code_hash FROM pairing_codes").fetchone()[0]
    assert code not in stored  # never the plaintext, hashed only (no-plaintext rule)


def test_a_leading_zero_code_survives_the_full_mint_and_consume_path(tmp_path, monkeypatch):
    """Leading zeros are legal codes. Anything that round-trips one through an int would drop
    them and make ~10% of the space silently unusable, so drive the real path rather than only
    asserting on the minted string's length."""
    conn = db.connect(tmp_path / "registry.db")
    monkeypatch.setattr(pairing, "_random_code", lambda: "000042")

    code = mint_pairing_code(conn)
    assert code == "000042"
    assert code_is_live(conn, code) is True
    assert consume_pairing_code(conn, code, "dev_1") is True


def test_minted_codes_stay_six_characters_across_many_mints(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    codes = {mint_pairing_code(conn) for _ in range(400)}
    assert all(len(c) == 6 and c.isdigit() for c in codes)


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


def test_unknown_code_is_not_live_but_a_minted_one_is(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    assert code_is_live(conn, code) is True
    assert code_is_live(conn, "000000" if code != "000000" else "111111") is False


def test_code_is_still_live_after_a_liveness_check(tmp_path):
    """`code_is_live` must not consume. The v0.4 handshake checks liveness before issuing a
    challenge; if that burned the code, a node could never complete the proof step."""
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    assert code_is_live(conn, code) is True
    assert consume_pairing_code(conn, code, "dev_1") is True


def test_attempt_budget_destroys_the_code_rather_than_cooling_it_down(tmp_path):
    """v0.4's online-guessing control: a small fixed budget, then permanent invalidation."""
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)

    for _ in range(4):
        assert burn_attempt(conn) == 0
        assert code_is_live(conn, code) is True

    assert burn_attempt(conn) == 1  # fifth failure destroys it
    assert code_is_live(conn, code) is False
    assert consume_pairing_code(conn, code, "dev_1") is False


def test_an_invalidated_code_never_comes_back(tmp_path):
    """Destroyed, not rate-limited — no amount of waiting revives it."""
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn, now_ms=0)
    for _ in range(5):
        burn_attempt(conn, now_ms=0)
    assert code_is_live(conn, code, now_ms=60 * 1000) is False
    assert consume_pairing_code(conn, code, "dev_1", now_ms=60 * 1000) is False


def test_wrong_guesses_burn_the_live_code_a_guesser_has_not_found_yet(tmp_path):
    """The decrement is deliberately not scoped to a code that matched: a guesser's wrong codes
    match no row, so a per-code-only counter would bound nothing at all."""
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    for _ in range(5):
        burn_attempt(conn)  # attacker guessing values that match nothing
    assert code_is_live(conn, code) is False


def test_burning_attempts_does_not_touch_an_already_consumed_code(tmp_path):
    conn = db.connect(tmp_path / "registry.db")
    code = mint_pairing_code(conn)
    assert consume_pairing_code(conn, code, "dev_1") is True
    assert burn_attempt(conn) == 0


def test_minting_reuses_the_slot_of_a_dead_code(tmp_path, monkeypatch):
    """`code_hash` is the primary key and the space is only 1,000,000 wide, so dead rows must not
    permanently consume it — at 128 bits this collision was unreachable, at six digits it is not."""
    conn = db.connect(tmp_path / "registry.db")
    monkeypatch.setattr(pairing, "_random_code", lambda: "424242")

    first = mint_pairing_code(conn, now_ms=0)
    assert consume_pairing_code(conn, first, "dev_1", now_ms=0) is True

    # Same code sampled again, previous row is dead: minting succeeds and the new row is live.
    second = mint_pairing_code(conn, now_ms=1000)
    assert second == "424242"
    assert code_is_live(conn, second, now_ms=1000) is True


def test_minting_resamples_past_a_live_code(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "registry.db")
    samples = iter(["313131", "313131", "595959"])
    monkeypatch.setattr(pairing, "_random_code", lambda: next(samples))

    first = mint_pairing_code(conn)
    second = mint_pairing_code(conn)  # first sample collides with a live code, resamples
    assert first == "313131"
    assert second == "595959"
    assert code_is_live(conn, first) is True
    assert code_is_live(conn, second) is True


def test_minting_gives_up_rather_than_returning_a_live_code(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "registry.db")
    monkeypatch.setattr(pairing, "_random_code", lambda: "777777")
    mint_pairing_code(conn)
    with pytest.raises(pairing.NoPairingCodeAvailableError):
        mint_pairing_code(conn)
