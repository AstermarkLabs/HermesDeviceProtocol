import pytest
from hdp_proto import ids
from hdp_proto.ids import InvalidULIDError


def test_new_returns_26_char_string():
    ulid = ids.new()
    assert isinstance(ulid, str)
    assert len(ulid) == 26


def test_new_is_valid():
    assert ids.is_valid(ids.new())


def test_parse_round_trips():
    ulid = ids.new()
    ts_ms, random_component = ids.parse(ulid)
    assert isinstance(ts_ms, int)
    assert isinstance(random_component, int)
    assert 0 <= random_component < (1 << 80)


def test_same_millisecond_ids_are_monotonic():
    # Mint a burst; even ids sharing a millisecond timestamp must still sort ascending, since
    # `id` doubles as an ordered dedupe key from M1 onward (FR-34).
    burst = [ids.new() for _ in range(500)]
    assert burst == sorted(burst)
    assert len(set(burst)) == len(burst)


def test_is_valid_rejects_garbage():
    assert not ids.is_valid("not-a-ulid")
    assert not ids.is_valid("")
    assert not ids.is_valid("0" * 25)
    assert not ids.is_valid("0" * 27)
    assert not ids.is_valid("!" * 26)


def test_parse_raises_invalid_ulid_error_on_garbage():
    with pytest.raises(InvalidULIDError):
        ids.parse("not-a-valid-ulid-string!!!")
