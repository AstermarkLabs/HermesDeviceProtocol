"""`device.status@1` (hdp-spec/capabilities/device.status@1.md).

Deliberately node-local and deliberately not what the `device_status_get` plugin tool calls —
see the capability doc's semantics section for the decision this reflects. Exercised only by the
conformance suite at M1.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from hdp_proto.capabilities import CapabilityDescriptor

DESCRIPTOR = CapabilityDescriptor(
    name="device.status",
    version=1,
    input_schema={"type": "object", "properties": {}},
    output_schema={
        "type": "object",
        "properties": {"platform": {"type": "string"}, "uptime_s": {"type": "number"}},
        "required": ["platform", "uptime_s"],
    },
)

_STARTED_AT = time.monotonic()


async def handle(args: dict[str, Any]) -> dict[str, Any]:
    return {"platform": sys.platform, "uptime_s": time.monotonic() - _STARTED_AT}
