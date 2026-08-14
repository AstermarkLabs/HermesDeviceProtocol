import pytest
from hdp_proto import ids
from hdp_proto.envelope import Envelope, EnvelopeError
from hdp_proto.version import HDP_VERSION


def _valid_wire(**overrides):
    base = {
        "hdp": HDP_VERSION,
        "type": "invoke",
        "id": ids.new(),
        "ts": 1736000000000,
        "corr": None,
        "payload": {"capability": "notifications.send"},
    }
    base.update(overrides)
    return base


def test_round_trip():
    original = Envelope.new("invoke", {"a": 1}, corr=ids.new())
    wire = original.to_wire()
    restored = Envelope.from_wire(wire)
    assert restored == original


def test_to_wire_is_a_dict_not_a_string():
    wire = Envelope.new("invoke", {}).to_wire()
    assert isinstance(wire, dict)
    assert wire["hdp"] == HDP_VERSION


def test_new_mints_a_valid_ulid_id():
    env = Envelope.new("invoke", {})
    assert ids.is_valid(env.id)


def test_from_wire_tolerates_unknown_fields():
    wire = _valid_wire()
    wire["some_future_field"] = "ignored"
    env = Envelope.from_wire(wire)
    assert env.type == "invoke"
    assert "some_future_field" not in env.to_wire()


@pytest.mark.parametrize(
    "overrides",
    [
        {"hdp": "1"},
        {"hdp": None},
        {"type": "not_a_real_type"},
        {"type": None},
        {"id": "not-a-ulid"},
        {"id": 12345},
        {"ts": "not-an-int"},
        {"ts": True},  # bool is a subclass of int — must be rejected explicitly
        {"payload": "not-a-dict"},
        {"payload": None},
        {"corr": 12345},
    ],
)
def test_from_wire_rejects_malformed_input(overrides):
    with pytest.raises(EnvelopeError):
        Envelope.from_wire(_valid_wire(**overrides))


def test_from_wire_rejects_non_dict():
    with pytest.raises(EnvelopeError):
        Envelope.from_wire("not a dict")  # type: ignore[arg-type]
