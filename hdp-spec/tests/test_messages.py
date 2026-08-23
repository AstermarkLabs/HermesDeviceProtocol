import pytest
from hdp_proto.capabilities import CapabilityDescriptor
from hdp_proto.messages import (
    Ack,
    CancelMsg,
    CapabilitiesMsg,
    ErrorMsg,
    Heartbeat,
    Hello,
    InvokeMsg,
    ProgressMsg,
    ResultMsg,
    RevokeMsg,
    Welcome,
)

_DESCRIPTOR = CapabilityDescriptor(
    name="diagnostics.echo",
    version=1,
    input_schema={"type": "object", "properties": {}, "required": []},
    output_schema={"type": "object", "properties": {}, "required": []},
)

# (instance, unknown-field key to inject for the tolerance test)
_CASES = [
    (
        Hello(hdp_versions=(0,), device_name="n", capabilities=(_DESCRIPTOR,), credential=None),
        "extra",
    ),
    (Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential="secret"), "extra"),
    (
        Hello(
            hdp_versions=(0,),
            device_name="n",
            capabilities=(),
            credential="secret",
            platform="android",
        ),
        "extra",
    ),
    (Welcome(hdp_version=0, device_id="01JB0000000000000000000000"), "extra"),
    (
        Welcome(hdp_version=0, device_id="01JB0000000000000000000000", credential="new-credential"),
        "extra",
    ),
    (CapabilitiesMsg(capabilities=(_DESCRIPTOR,)), "extra"),
    (
        InvokeMsg(
            capability="diagnostics.echo", version=1, args={"payload": {}}, deadline_ms=30_000
        ),
        "extra",
    ),
    (Ack(), "extra"),
    (ResultMsg(ok=True, data={"payload": {}}, error=None), "extra"),
    (
        ResultMsg(
            ok=False, data=None, error={"code": "bridge_unavailable", "message": "m", "hint": "h"}
        ),
        "extra",
    ),
    (CancelMsg(reason="timeout"), "extra"),
    (ProgressMsg(detail={"pct": 50}), "extra"),
    (Heartbeat(), "extra"),
    (ErrorMsg(code="bridge_unavailable", message="m", hint="h"), "extra"),
    (RevokeMsg(reason="credential rotated"), "extra"),
]


@pytest.mark.parametrize("instance,_extra_key", _CASES)
def test_round_trip(instance, _extra_key):
    cls = type(instance)
    wire = instance.to_wire()
    restored = cls.from_wire(wire)
    assert restored == instance


@pytest.mark.parametrize("instance,extra_key", _CASES)
def test_from_wire_tolerates_unknown_fields(instance, extra_key):
    cls = type(instance)
    wire = instance.to_wire()
    wire[extra_key] = "ignored"
    restored = cls.from_wire(wire)
    assert restored == instance


def test_welcome_credential_defaults_to_none_and_round_trips_present_as_null():
    welcome = Welcome(hdp_version=0, device_id="01JB0000000000000000000000")
    assert welcome.credential is None
    wire = welcome.to_wire()
    assert "credential" in wire
    assert wire["credential"] is None
    assert Welcome.from_wire(wire).credential is None


def test_hello_platform_defaults_to_none_and_round_trips_present_as_null():
    """Amendments v0.3. Emitting the key as an explicit null (rather than omitting it) keeps
    `to_wire` output shape-stable across nodes that do and don't report a platform."""
    hello = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=None)
    assert hello.platform is None
    wire = hello.to_wire()
    assert "platform" in wire
    assert wire["platform"] is None
    assert Hello.from_wire(wire).platform is None


def test_hello_without_platform_key_parses_as_none():
    """A pre-v0.3 node omits the key entirely; that must stay a valid `hello`, not a wire break."""
    wire = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential="c").to_wire()
    del wire["platform"]
    assert Hello.from_wire(wire).platform is None


def test_hello_rejects_non_string_platform():
    """Optional, not untyped — same posture as a non-string `credential`."""
    wire = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential="c").to_wire()
    wire["platform"] = 17
    with pytest.raises(ValueError):
        Hello.from_wire(wire)


def test_hello_rejects_malformed_hdp_versions():
    wire = Hello(hdp_versions=(0,), device_name="n", capabilities=(), credential=None).to_wire()
    wire["hdp_versions"] = "not-a-list"
    with pytest.raises(ValueError):
        Hello.from_wire(wire)


def test_invoke_msg_rejects_missing_deadline():
    wire = InvokeMsg(capability="c", version=1, args={}, deadline_ms=1000).to_wire()
    del wire["deadline_ms"]
    with pytest.raises(ValueError):
        InvokeMsg.from_wire(wire)


def test_result_msg_rejects_non_bool_ok():
    wire = {"ok": "yes", "data": None, "error": None}
    with pytest.raises(ValueError):
        ResultMsg.from_wire(wire)
