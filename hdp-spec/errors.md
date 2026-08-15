# HDP error taxonomy

This is the normative enumeration of every HDP error code. The executable copy lives in
`hdp_proto/errors.py`'s `ErrorCode` enum and `HINTS` dict; `hdp-spec/tests/test_errors_conformance.py`
asserts the two are identical — code set, declaration order, and hint text (FR-32). Do not add,
remove, reorder, or reword an entry here without making the matching change in `errors.py`, and
vice versa.

Each entry lists: the code, when it is emitted, whether it is terminal (ends the invocation from
the caller's point of view), whether it is model-visible (returned in a tool result) or log-only
(written to the log but never surfaced to the model), and the hint text the model receives when
the code is model-visible.

## `bridge_unavailable`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the HDP runtime failed to start, or an unexpected exception escaped a handler
  before a real result could be produced (M0/M1: also the fallback for any transport-level failure
  that has no more specific code).
- **Hint:** The HDP runtime failed to start or is not responding. Retry shortly, or call
  device_status_get to check bridge health.

## `not_implemented`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the requested operation is reserved but not implemented at the current
  milestone (e.g. `resolve_approval` before M3).
- **Hint:** This capability is reserved but not implemented in the MVP.

## `no_matching_device`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** capability resolution found zero paired devices advertising the requested
  capability.
- **Hint:** No paired device advertises this capability. Call device_status_get to see connected
  devices and their capabilities.

## `capability_unsupported`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** an explicit `device` was named but that device does not advertise the
  requested capability.
- **Hint:** The named device does not advertise this capability. Call device_status_get to see
  what it supports.

## `ambiguous_device`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** more than one paired device advertises the requested capability and no
  explicit `device` was given to disambiguate. (M1 only reaches the zero-node and single-node
  cases; the multi-node selection path that actually raises this is M4.)
- **Hint:** Multiple devices advertise this capability. Pass an explicit device, or call
  device_status_get to see the candidates.

## `device_offline`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the resolved device never acknowledged the invocation within the 5s ack
  timeout, or disconnected (missed heartbeat / WS close) while an invocation was in flight for it.
- **Hint:** The device disconnected or missed its heartbeat. Call device_status_get to check
  current online state.

## `invocation_timeout`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the device acknowledged the invocation but no result arrived before the
  execution deadline elapsed.
- **Hint:** The device did not respond within its deadline. Retry, or call device_status_get to
  check whether it is still online.

## `malformed_result`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** a result arrived but failed output-schema validation against the capability's
  advertised (or documented) output schema — including the case where the advertised schema
  itself no longer matches what the capability actually returns (schema drift; see `schema_drift`
  below for the paired log-only record of that same event).
- **Hint:** The device returned a result that failed schema validation. Treat the capability as
  unreliable until the device reconnects.

## `version_incompatible`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the node's advertised capability version has no mutually supported version
  with what the bridge/plugin expects, or the node's `hello.hdp_versions` shares no version with
  the bridge's supported set.
- **Hint:** No mutually supported capability version. Call device_status_get to see the device's
  advertised versions.

## `auth_failed`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the device credential was rejected. Unreachable at M1 — the bridge accepts any
  credential value (including absent) until M2's real pairing/auth lands.
- **Hint:** The device credential was rejected. Re-pair the device.

## `policy_denied`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** policy denies this capability for this device. Unreachable at M1 — the policy
  call site is an allow-all stub until M3.
- **Hint:** Policy denies this capability for this device. An operator can change the policy; the
  model cannot.

## `approval_denied`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** a human denied the invocation via the approval flow. Unreachable until M3.
- **Hint:** A human denied this invocation.

## `approval_timeout`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** no approval decision arrived before the approval window expired. Unreachable
  until M3.
- **Hint:** No approval decision arrived before the approval window expired. Ask again if the
  action is still wanted.

## `revoked`
- **Terminal:** yes
- **Model-visible:** yes
- **When emitted:** the device's credential was revoked mid-invocation. Unreachable until M2 (the
  `revoke` wire message is defined at M1 but unused).
- **Hint:** The device's credential was revoked mid-invocation.

## `late_result`
- **Terminal:** n/a (recorded after the invocation already reached a terminal state)
- **Model-visible:** no — log-only
- **When emitted:** a `result` frame arrives whose `invocation_id` is not in the pending table
  (already resolved, timed out, or cancelled). The plugin drops it silently; the bridge logs this
  code.
- **Hint:** A result arrived for an invocation that already reached a terminal state; it was
  dropped.

## `schema_drift`
- **Terminal:** n/a (log-only companion to a `malformed_result` the model does see)
- **Model-visible:** no — log-only
- **When emitted:** a result fails output-schema validation specifically because the node's
  advertised schema no longer matches what it actually returns, as distinct from an arbitrary
  malformed payload. Logged alongside the model-visible `malformed_result`.
- **Hint:** The device's advertised schema no longer matches what it returns.
