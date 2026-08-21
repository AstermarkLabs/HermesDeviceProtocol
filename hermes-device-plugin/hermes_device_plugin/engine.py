"""The plugin-side entry to daemon-owned invocation-time resolution."""

from __future__ import annotations

import json
from typing import Any

from hdp_proto.errors import ErrorCode, err, ok

from . import config
from .runtime import get_runtime
from .transport.base import InvokeRequest


async def invoke(
    capability: str,
    acceptable_versions: list[int],
    args: dict[str, Any],
    meta: dict[str, Any],
    *,
    device_id: str | None = None,
) -> str:
    """Forward one unresolved request and return the daemon's model-facing result."""
    runtime = get_runtime()
    node_args = dict(args)
    node_args.pop("device", None)
    request = InvokeRequest(
        capability=capability,
        acceptable_versions=tuple(acceptable_versions),
        requested_device_id=device_id,
        args=node_args,
        deadline_ms=config.DEFAULT_INVOCATION_DEADLINE_MS,
        meta=meta,
    )
    result = await runtime.transport.invoke(request)
    if not result.ok:
        if result.error is not None:
            return json.dumps({"ok": False, "error": result.error})
        return json.dumps(err(ErrorCode.BRIDGE_UNAVAILABLE, "transport failure"))
    return json.dumps(ok(result.data or {}))
