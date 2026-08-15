"""`diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure round-trip."""

from __future__ import annotations

from typing import Any

from hdp_proto.capabilities import CapabilityDescriptor

DESCRIPTOR = CapabilityDescriptor(
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


async def handle(args: dict[str, Any]) -> dict[str, Any]:
    return {"payload": args.get("payload", {})}
