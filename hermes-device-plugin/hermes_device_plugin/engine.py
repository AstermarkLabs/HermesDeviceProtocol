"""`invoke()` — the one path every device tool shares (design §2.3).

Ten numbered steps, present as real steps even where a step is trivial against the M0 loopback
stub — each trivial step says in a comment which milestone fills it, so this file reads as
scaffolding rather than an unfinished implementation (docs/m0-plan.md §5.5). Runs *on the HDP
loop*: callers reach this coroutine only via `runtime.get_runtime().submit(engine.invoke(...))`,
so it is safe to call `get_runtime().transport` directly from inside it.
"""

from __future__ import annotations

import json
from typing import Any

from hdp_proto.errors import ErrorCode, err, ok

from . import config
from .runtime import get_runtime
from .transport.base import InvokeRequest


def _policy_check_stub(device_id: str, capability: str) -> bool:
    """Step 4's call site — the allow-all stub, present from day one (design §2.3) specifically
    so M3 fills in a real function rather than threading a new parameter through nine layers.
    Signature takes a resolved `device_id`, not a candidate list — the shape m4-plan's target-
    selection work depends on already being right. Always ALLOW at M0/M1/M2 (m3-plan Day 1
    deletes this stub)."""
    return True


async def invoke(
    capability: str,
    acceptable_versions: list[int],
    args: dict[str, Any],
    meta: dict[str, Any],
    *,
    device_id: str | None = None,
) -> str:
    """Resolve a device, check policy, invoke, and return the model-facing JSON result string."""
    runtime = get_runtime()

    # 1. capability + acceptable version list — the caller's arguments, carried as-is; no
    #    version negotiation exists yet (M4, FR-7).
    # 1b. capture policy snapshot — trivial against the allow-all stub; a real snapshot lands
    #     with m3-plan's policy engine (captured before selection, per m3-plan §3.3 amended).

    # 2. resolve target device. The M0/M1 stub registry is always empty, so this is the one
    #    failure path M0 can genuinely exercise (D3): every call — named device or not — ends in
    #    no_matching_device, with FR-5's hint naming device_status_get as the recovery action.
    #    M1 adds real candidates; M4 adds >1-candidate resolution (ambiguous_device / configured
    #    default_device) and the explicit-device-lacks-capability branch (capability_unsupported).
    devices = await runtime.transport.list_devices()
    candidates = [d for d in devices if d.device_id == device_id] if device_id else devices
    if not candidates:
        return json.dumps(
            err(ErrorCode.NO_MATCHING_DEVICE, "no paired device advertises this capability")
        )
    resolved_device = candidates[0]

    # 3. negotiate capability version — trivial at M0: one entry in, one entry out. M4 adds
    #    highest-mutually-supported selection and version_incompatible on no overlap (FR-7).
    version = acceptable_versions[0]

    # 4. policy.check(...) — the M0/M1 allow-all stub, called unconditionally so the call site
    #    is exercised from day one (design §2.3, m3-plan Day 1).
    if not _policy_check_stub(resolved_device.device_id, capability):
        return json.dumps(err(ErrorCode.POLICY_DENIED, "denied by policy"))

    # 5. ASK → pending_approval — unreachable: the stub's policy decision is never ASK. Lands M3.

    # 6. mint invocation_id — happens inside transport.invoke() (bridge-minted, FR-28; see
    #    transport/base.py's InvokeRequest docstring for why the mint lives there and not here).
    # 7. transport.invoke(...) with a deadline.
    request = InvokeRequest(
        capability=capability,
        version=version,
        device_id=resolved_device.device_id,
        args=args,
        deadline_ms=config.DEFAULT_INVOCATION_DEADLINE_MS,
        meta=meta,
    )
    result = await runtime.transport.invoke(request)

    # 8. await result / timeout / cancellation — await only at M0; real deadlines and
    #    cancellation are M1 (FR-33).
    # 9. validate result against the capability's output schema — trivial at M0 (nothing to
    #    validate against yet); real validation lands M1 (FR-31, malformed_result).
    # 10. audit terminal state, return the JSON string — no audit writer exists until M2; M0
    #     returns the result directly.
    if not result.ok:
        if result.error is not None:
            return json.dumps({"ok": False, "error": result.error})
        return json.dumps(err(ErrorCode.BRIDGE_UNAVAILABLE, "transport failure"))
    return json.dumps(ok(result.data or {}))
