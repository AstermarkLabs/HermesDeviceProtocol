"""Capability descriptors and output-schema validation.

`CapabilityDescriptor` is the wire shape a `capabilities` message's list entries take
(hdp-spec/HDP-0.md §6) — `name`, `version`, `input_schema`, `output_schema`, the last two being
plain JSON Schema objects. `validate_output` is a small, stdlib-only structural checker used by
both the node (before sending a `result`) and the bridge (before trusting one) — SDR-3's
stdlib-only discipline rules out a `jsonschema` dependency here just as it did for `hdp_proto`'s
other modules, so this checker only supports the subset of JSON Schema the MVP's three
capability documents actually use: `type` in {object, string, number, integer, boolean, array},
`properties`, `required`, and `items`. A schema that needs more than that is a signal M2+ should
reconsider this trade-off, not a reason to quietly extend it here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaValidationError(ValueError):
    """Raised by `validate_output` when `data` does not match `output_schema`. The caller is
    responsible for translating this into `ErrorCode.MALFORMED_RESULT` (and, when the mismatch is
    specifically "advertised schema no longer matches reality", the paired log-only
    `ErrorCode.SCHEMA_DRIFT` record) — this module knows nothing about the error taxonomy."""


@dataclass(frozen=True)
class CapabilityDescriptor:
    """One entry in a `capabilities` message's full-replacement list (HDP-0.md §2, §6)."""

    name: str
    version: int
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    @classmethod
    def from_wire(cls, d: dict[str, Any]) -> CapabilityDescriptor:
        """Never `cls(**d)` — read fields by name, tolerate unknown fields, matching the
        discipline `envelope.py` established at M0."""
        if not isinstance(d, dict):
            raise ValueError(f"capability descriptor must be an object, got {type(d).__name__}")

        name = d.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"invalid capability name: {name!r}")

        version = d.get("version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError(f"invalid capability version: {version!r}")

        input_schema = d.get("input_schema")
        if not isinstance(input_schema, dict):
            raise ValueError(f"invalid capability input_schema: {type(input_schema).__name__}")

        output_schema = d.get("output_schema")
        if not isinstance(output_schema, dict):
            raise ValueError(f"invalid capability output_schema: {type(output_schema).__name__}")

        return cls(
            name=name, version=version, input_schema=input_schema, output_schema=output_schema
        )

    def to_wire(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


def validate_output(descriptor: CapabilityDescriptor, data: Any) -> None:
    """Validate `data` against `descriptor.output_schema`. Raises `SchemaValidationError` on any
    mismatch; returns `None` (never a truthy/falsy "is valid" value — a caller that forgets to
    check a boolean return is exactly the bug this shape avoids) on success."""
    _validate(descriptor.output_schema, data, "$")


def _validate(schema: dict[str, Any], value: Any, path: str) -> None:
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path}: expected object, got {type(value).__name__}")
        for field in schema.get("required", []):
            if field not in value:
                raise SchemaValidationError(f"{path}: missing required field {field!r}")
        properties = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in value:
                _validate(sub_schema, value[key], f"{path}.{key}")

    elif schema_type == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path}: expected string, got {type(value).__name__}")

    elif schema_type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected boolean, got {type(value).__name__}")

    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected integer, got {type(value).__name__}")

    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected number, got {type(value).__name__}")

    elif schema_type == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path}: expected array, got {type(value).__name__}")
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(value):
                _validate(items_schema, item, f"{path}[{i}]")

    # A schema with no `type` (or a type this checker doesn't model) accepts any value — this is
    # the deliberate escape hatch `diagnostics.echo@1`'s untyped `payload` field relies on, not an
    # oversight.
