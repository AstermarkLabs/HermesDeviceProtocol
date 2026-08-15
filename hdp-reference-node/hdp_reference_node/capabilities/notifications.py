"""`notifications.send@1` (hdp-spec/capabilities/notifications.send@1.md).

Prints the title and body to stdout — this is the literal exit-gate check (m1-plan.md §8 step 2:
"the node process prints the title and body"), not a real notification UI.
"""

from __future__ import annotations

from typing import Any

from hdp_proto.capabilities import CapabilityDescriptor

DESCRIPTOR = CapabilityDescriptor(
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


async def handle(args: dict[str, Any]) -> dict[str, Any]:
    title = args.get("title", "")
    body = args.get("body", "")
    print(f"{title}\n{body}")
    return {"delivered": True}
