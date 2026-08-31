import pytest
from hdp_proto import ids
from hdp_proto.envelope import Envelope, EnvelopeError, UnknownTypeError, UnsupportedVersionError
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


@pytest.mark.parametrize("overrides", [{"hdp": "1"}, {"hdp": None}, {"hdp": "99"}])
def test_version_mismatch_raises_the_specific_subclass(overrides):
    """HDP-0.md §3: a version mismatch must be distinguishable from an unknown type, because the
    connection layer reacts differently (close vs. reply-and-stay-open)."""
    with pytest.raises(UnsupportedVersionError):
        Envelope.from_wire(_valid_wire(**overrides))


@pytest.mark.parametrize("overrides", [{"type": "not_a_real_type"}, {"type": None}])
def test_unknown_type_raises_the_specific_subclass(overrides):
    with pytest.raises(UnknownTypeError):
        Envelope.from_wire(_valid_wire(**overrides))


@pytest.mark.parametrize(
    "message_type",
    [
        "ctl_policy_show",
        "ctl_policy_show_reply",
        "ctl_policy_reload",
        "ctl_policy_reload_reply",
        "ctl_usb_bootstrap",
        "ctl_usb_bootstrap_reply",
    ],
)
def test_operator_policy_control_types_are_known(message_type):
    """M3 policy inspection stays on the daemon control plane, never a plugin file read."""
    assert Envelope.from_wire(_valid_wire(type=message_type)).type == message_type


def test_both_subclasses_are_still_catchable_as_envelope_error():
    with pytest.raises(EnvelopeError):
        Envelope.from_wire(_valid_wire(hdp="1"))
    with pytest.raises(EnvelopeError):
        Envelope.from_wire(_valid_wire(type="bogus"))
