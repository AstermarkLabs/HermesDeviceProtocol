"""The closed HDP error-code taxonomy and the model-facing result envelope.

`ErrorCode` is the **one** place an error-code string is spelled in the repo (docs/m0-plan.md
§4.3). Every emission site — `engine.py`, `tools.py`, and eventually `hdp-bridge` — imports a
member from here rather than writing a string literal, so the M1 conformance test that asserts
`errors.py` <-> `hdp-spec/errors.md` byte-for-byte parity has something to check.

The set below is the **full** taxonomy already enumerated across `docs/design.md` §5 and
`docs/requirements.md`. Declaring it all now (M0-plan §4.3 permits this) is not the same as
landing it: only `BRIDGE_UNAVAILABLE`, `NOT_IMPLEMENTED`, and `NO_MATCHING_DEVICE` are reachable
against the M0 loopback stub (no node, no socket, no registry, no policy, no deadlines). The rest
become reachable as their owning milestone lands its wire, registry, or policy engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable declaration order — this is the order the M1 conformance test diffs against
    `errors.md`, so it is not alphabetized and not reordered casually."""

    # Reachable at M0, against the loopback stub.
    BRIDGE_UNAVAILABLE = "bridge_unavailable"
    NOT_IMPLEMENTED = "not_implemented"
    NO_MATCHING_DEVICE = "no_matching_device"

    # Land at M1 — invocation lifecycle, real wire, real node.
    CAPABILITY_UNSUPPORTED = "capability_unsupported"
    AMBIGUOUS_DEVICE = "ambiguous_device"
    DEVICE_OFFLINE = "device_offline"
    INVOCATION_TIMEOUT = "invocation_timeout"
    MALFORMED_RESULT = "malformed_result"
    VERSION_INCOMPATIBLE = "version_incompatible"

    # Land at M2/M3 — pairing, credentials, policy.
    AUTH_FAILED = "auth_failed"
    POLICY_DENIED = "policy_denied"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_TIMEOUT = "approval_timeout"
    REVOKED = "revoked"

    # Log-only — never returned to the model, asserted only against audit/bridge logs.
    LATE_RESULT = "late_result"
    SCHEMA_DRIFT = "schema_drift"


HINTS: dict[ErrorCode, str] = {
    ErrorCode.BRIDGE_UNAVAILABLE: "The HDP runtime failed to start or is not responding. Retry "
    "shortly, or call device_status_get to check bridge health.",
    ErrorCode.NOT_IMPLEMENTED: "This capability is reserved but not implemented in the MVP.",
    ErrorCode.NO_MATCHING_DEVICE: "No paired device advertises this capability. Call "
    "device_status_get to see connected devices and their capabilities.",
    ErrorCode.CAPABILITY_UNSUPPORTED: "The named device does not advertise this capability. "
    "Call device_status_get to see what it supports.",
    ErrorCode.AMBIGUOUS_DEVICE: "Multiple devices advertise this capability. Pass an explicit "
    "device, or call device_status_get to see the candidates.",
    ErrorCode.DEVICE_OFFLINE: "The device disconnected or missed its heartbeat. Call "
    "device_status_get to check current online state.",
    ErrorCode.INVOCATION_TIMEOUT: "The device did not respond within its deadline. Retry, or "
    "call device_status_get to check whether it is still online.",
    ErrorCode.MALFORMED_RESULT: "The device returned a result that failed schema validation. "
    "Treat the capability as unreliable until the device reconnects.",
    ErrorCode.VERSION_INCOMPATIBLE: "No mutually supported capability version. Call "
    "device_status_get to see the device's advertised versions.",
    ErrorCode.AUTH_FAILED: "The device credential was rejected. Re-pair the device.",
    ErrorCode.POLICY_DENIED: "Policy denies this capability for this device. An operator can "
    "change the policy; the model cannot.",
    ErrorCode.APPROVAL_DENIED: "A human denied this invocation.",
    ErrorCode.APPROVAL_TIMEOUT: "No approval decision arrived before the approval window "
    "expired. Ask again if the action is still wanted.",
    ErrorCode.REVOKED: "The device's credential was revoked mid-invocation.",
    ErrorCode.LATE_RESULT: "A result arrived for an invocation that already reached a terminal "
    "state; it was dropped.",
    ErrorCode.SCHEMA_DRIFT: "The device's advertised schema no longer matches what it returns.",
}
"""Every member has a non-empty hint, but FR-5 ("every hint names a recovery action") is an M1
requirement — see requirements.md FR-5's Verify line — not asserted here."""


@dataclass(frozen=True)
class Error:
    """The `error` half of the model-facing result envelope."""

    code: ErrorCode
    message: str
    hint: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message, "hint": self.hint}


def ok(data: dict[str, Any]) -> dict[str, Any]:
    """Build the success half of the model-facing result envelope: `{"ok": true, "data": {...}}`."""
    return {"ok": True, "data": data}


def err(code: ErrorCode, detail: BaseException | str, *, hint: str | None = None) -> dict[str, Any]:
    """Build the failure half of the model-facing result envelope.

    `detail` becomes `message` (for a human reading a log); `hint` defaults to the code's
    canonical recovery hint from `HINTS` and is written for the model, not the human (FR-5).
    """
    message = str(detail)
    resolved_hint = hint if hint is not None else HINTS.get(code, "")
    return {"ok": False, "error": Error(code=code, message=message, hint=resolved_hint).to_dict()}
