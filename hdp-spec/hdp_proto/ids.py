"""Hand-rolled ULID mint/parse — stdlib only, no `ulid` dependency (SDR-3).

A ULID is a 48-bit millisecond timestamp followed by 80 bits of randomness, Crockford
base32-encoded to 26 characters. Two ids minted in the same process within the same millisecond
still sort correctly, because the random component is generated as one 80-bit integer and
incremented (not re-randomized) when the millisecond hasn't advanced since the last mint in this
process. That monotonicity is what makes `Envelope.id` usable later as an ordered dedupe key
(FR-34, M1) — it is not optional polish.
"""

from __future__ import annotations

import os
import threading
import time

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_BITS = 48
_RANDOM_BITS = 80
_RANDOM_MASK = (1 << _RANDOM_BITS) - 1

_lock = threading.Lock()
_last: tuple[int, int] | None = None  # (ts_ms, random_component) of the last-minted id


class InvalidULIDError(ValueError):
    """Raised by `parse` on a string that is not a well-formed 26-character ULID."""


def _encode_crockford(value: int, length: int) -> str:
    chars = ["0"] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def _decode_crockford(text: str) -> int:
    value = 0
    for ch in text.upper():
        try:
            digit = _CROCKFORD_ALPHABET.index(ch)
        except ValueError as exc:
            raise InvalidULIDError(f"invalid Crockford base32 character: {ch!r}") from exc
        value = (value << 5) | digit
    return value


def new() -> str:
    """Mint a new ULID, monotonic within this process for same-millisecond calls."""
    global _last
    with _lock:
        ts_ms = int(time.time() * 1000)
        if _last is not None and ts_ms <= _last[0]:
            # Same (or non-monotonic) millisecond: bump the previous random component by one
            # instead of drawing fresh randomness, so ordering is preserved.
            last_ts_ms, last_random = _last
            ts_ms = last_ts_ms
            random_component = (last_random + 1) & _RANDOM_MASK
        else:
            random_component = int.from_bytes(os.urandom(10), "big") & _RANDOM_MASK
        _last = (ts_ms, random_component)

    # 48-bit timestamp (10 base32 chars) + 80-bit randomness (16 base32 chars) = 26 chars.
    return _encode_crockford(ts_ms, 10) + _encode_crockford(random_component, 16)


def parse(ulid: str) -> tuple[int, int]:
    """Parse a ULID string into (timestamp_ms, random_component). Raises InvalidULIDError."""
    if len(ulid) != 26:
        raise InvalidULIDError(f"expected 26 characters, got {len(ulid)}")
    ts_part, random_part = ulid[:10], ulid[10:]
    ts_ms = _decode_crockford(ts_part)
    if ts_ms >= (1 << _TIME_BITS):
        raise InvalidULIDError("timestamp component out of range")
    random_component = _decode_crockford(random_part)
    return ts_ms, random_component


def is_valid(ulid: str) -> bool:
    try:
        parse(ulid)
    except InvalidULIDError:
        return False
    return True
