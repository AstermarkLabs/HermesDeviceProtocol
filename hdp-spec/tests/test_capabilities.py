import pytest
from hdp_proto.capabilities import CapabilityDescriptor, SchemaValidationError, validate_output

ECHO_DESCRIPTOR = CapabilityDescriptor(
    name="diagnostics.echo",
    version=1,
    input_schema={
        "type": "object",
        "properties": {"payload": {"type": "object"}},
        "required": ["payload"],
    },
    output_schema={
        "type": "object",
        "properties": {"payload": {"type": "object"}},
        "required": ["payload"],
    },
)

NOTIFICATIONS_DESCRIPTOR = CapabilityDescriptor(
    name="notifications.send",
    version=1,
    input_schema={
        "type": "object",
        "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
        "required": ["title", "body"],
    },
    output_schema={
        "type": "object",
        "properties": {"delivered": {"type": "boolean"}},
        "required": ["delivered"],
    },
)


def test_round_trip():
    wire = NOTIFICATIONS_DESCRIPTOR.to_wire()
    restored = CapabilityDescriptor.from_wire(wire)
    assert restored == NOTIFICATIONS_DESCRIPTOR


def test_from_wire_tolerates_unknown_fields():
    wire = NOTIFICATIONS_DESCRIPTOR.to_wire()
    wire["some_future_field"] = "ignored"
    restored = CapabilityDescriptor.from_wire(wire)
    assert restored.name == "notifications.send"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": None},
        {"name": ""},
        {"version": "not-an-int"},
        {"version": True},
        {"input_schema": "not-a-dict"},
        {"output_schema": "not-a-dict"},
    ],
)
def test_from_wire_rejects_malformed_input(overrides):
    wire = NOTIFICATIONS_DESCRIPTOR.to_wire()
    wire.update(overrides)
    with pytest.raises(ValueError):
        CapabilityDescriptor.from_wire(wire)


def test_validate_output_accepts_matching_data():
    validate_output(NOTIFICATIONS_DESCRIPTOR, {"delivered": True})


def test_validate_output_rejects_missing_required_field():
    with pytest.raises(SchemaValidationError):
        validate_output(NOTIFICATIONS_DESCRIPTOR, {})


def test_validate_output_rejects_wrong_type():
    with pytest.raises(SchemaValidationError):
        validate_output(NOTIFICATIONS_DESCRIPTOR, {"delivered": "yes"})


def test_validate_output_untyped_nested_field_accepts_anything():
    """diagnostics.echo@1's `payload` field has no nested schema — any JSON value round-trips."""
    validate_output(ECHO_DESCRIPTOR, {"payload": {"nested": [1, 2, {"a": "b"}]}})


def test_validate_output_rejects_non_object_top_level():
    with pytest.raises(SchemaValidationError):
        validate_output(NOTIFICATIONS_DESCRIPTOR, "not a dict")
