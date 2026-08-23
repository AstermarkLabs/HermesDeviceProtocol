# Android Node Contract

This document is the M5 handoff for an Android implementation of an HDP node. It is
normative at the protocol boundary: an Android node must produce and consume the same HDP/0
frames and observable outcomes as any other node. Kotlin, Android modules, UI, storage APIs,
and lifecycle components remain implementation choices in the downstream Android project.

The normative sources are [`hdp-spec/HDP-0.md`](../hdp-spec/HDP-0.md),
[`hdp-spec/errors.md`](../hdp-spec/errors.md), and the capability documents under
[`hdp-spec/capabilities/`](../hdp-spec/capabilities/). This handoff intentionally does not
reference Python classes as an implementation contract.

## Scope and first capability profile

The first Android node advertises exactly these capabilities:

| Capability | Role | Android behavior |
|---|---|---|
| `notifications.send@1` | action | Display a local notification only when both bridge policy and Android notification permission/local policy allow it. |
| `device.status@1` | diagnostic | Return the capability's schema-valid status data; never expose the credential. |

`diagnostics.echo@1` and all sensitive capabilities are outside the first Android profile. An
unknown or unimplemented capability is denied locally with the existing structured HDP error
shape; it is never accepted merely because the bridge sent an `invoke` frame.

The capability schemas and versioning rules are those in the two normative capability documents.
The bridge's `device` routing field is not sent to the node.

## Wire contract

The node uses a WebSocket HDP endpoint and sends one `hello` envelope on every new connection.
The `hello` payload contains `hdp_versions: [0]`, a user-visible `device_name`, the complete
current capability descriptor list, and either the stored credential or the explicit `pair:`
credential for first pairing. Unsupported protocol versions are rejected; the node must not
downgrade silently.

The Android node also sends `platform: "android"` (HDP-0.md Amendments v0.3). This is advisory
metadata that makes the node distinguishable in `device_status_get` and `hermes hdp devices`; it is
never an authorization input, and omitting it degrades to a `"unknown"` listing rather than failing
the handshake.

The Android node generates a non-exportable EC P-256 key pair in the Android Keystore before its
first pairing and sends the public half as `device_pubkey` (base64 DER `SubjectPublicKeyInfo`).
Doing so opts into the v0.4 device-bound handshake, which the Android profile requires:

1. Node sends `hello` carrying `device_pubkey` and the `pair:`-prefixed code.
2. Bridge replies `challenge` with a fresh nonce.
3. Node signs `"HDP/0 pair-challenge\x00" + nonce` with the Keystore private key and returns
   `proof`.
4. Only then does the bridge consume the pairing code, bind the key to the new `device_id`, and
   send `welcome`.

Every later reconnect repeats the exchange with the `"HDP/0 auth-challenge\x00"` context, so
authentication requires **both** the stored credential and possession of the Keystore key. The
private key must never be exportable, never leave the Keystore, and never appear in a backup — the
credential rules below apply to it in full. A credential copied off the device is useless without
it, which is the point.

The pairing code itself is six digits. A live code tolerates only a small number of failed attempts
before the bridge destroys it permanently, so the node must not retry a rejected code automatically;
surface the failure and let the user request a fresh code.

On success, the bridge sends `welcome` with the negotiated `hdp_version` and `device_id`. The
first pairing welcome contains the credential exactly once. The node writes it immediately to
platform-protected storage and never logs it, includes it in diagnostics, or stores it in an
ordinary preference, database, backup, or crash report. Returning connections send the stored
credential and receive no new plaintext credential.

`hello` is also the initial full capability advertisement. A later `capabilities` frame is a
complete replacement, never a delta. Build the new immutable set, validate it, and publish it as
one state transition; do not clear the old set and add entries one at a time.

For `invoke`, the node must:

1. Check that the capability and exact version are in the current local allowlist.
2. Check the Android runtime permission required by the capability.
3. Send `ack` and dispatch only after those checks pass.
4. Validate the result against the advertised output schema before sending `result`.
5. Return the existing structured error taxonomy for denial or failure.

The bridge policy decision remains authoritative before transmission. A local grant cannot
override a bridge denial, and a bridge grant cannot override local policy or Android permission
denial. The node must never turn a denial into a retry loop.

`cancel` is best effort. Track cancelled invocation IDs before dispatch completes; a cancelled
or unknown ID must not execute and a late result must not be emitted. A `revoke` frame invalidates
the local session, transitions the node to `REVOKED`, closes the socket, and prevents reconnect
until the user completes a new pairing flow.

## State model

The node owns the following durable or process-local state:

| State | Lifetime | Rule |
|---|---|---|
| `device_id` | durable after pairing | Use the bridge-issued ID as an opaque identifier; do not generate a replacement on reconnect. |
| credential | durable, protected | Store only in Android Keystore-backed storage or an equivalent hardware/platform-protected secret store. |
| connection state | process-local | `IDLE`, `CONNECTING`, `ONLINE`, `OFFLINE`, `REVOKED`, or `INCOMPATIBLE`. |
| capability set | process-local, rebuilt on connect | Keep the complete current set and re-advertise it after reconnect. |
| in-flight IDs | process-local | Remove on every terminal path: success, error, timeout, cancellation, disconnect, or revoke. |
| reconnect attempt | process-local | Reset after a successful welcome; do not retry terminal auth or version failures. |
| local policy | durable configuration | Default to deny; require an explicit local allowlist and current Android permission. |

Process death loses sockets and in-flight calls, not identity or credentials. On restart, the node
starts `CONNECTING` with the stored credential. It must report abandoned calls as unavailable
locally rather than replaying them. Network loss and bridge restart are normal `OFFLINE` states,
not revocation.

Reconnect delays use bounded exponential backoff with jitter: 1 second, 2 seconds, 4 seconds,
and so on up to a 30-second base, with a small randomized positive offset. Reset the schedule
after a successful handshake. Do not retry an `auth_failed`/revoked credential or an unsupported
protocol version; those require user-visible recovery.

## Android lifecycle and security guidance

Foreground operation may hold the realtime connection. Background operation must tolerate socket
suspension and process death. A foreground service is appropriate only for an explicitly selected
persistent-device mode with a demonstrated continuous-availability requirement; it is not a
protocol requirement.

When the app returns to the foreground or the network becomes available, reconnect using the
protected credential and re-advertise the full capability set. A notification may explain that
the node is offline, but a wake path must not silently retry a privileged invocation outside the
normal bridge-policy and node-policy path.

Credential handling requirements:

- use Android Keystore-backed protection (or an equivalent platform-protected secret facility);
- exclude credentials from logs, analytics, backups, screenshots, clipboard, and crash reports;
- use restrictive process/file permissions for any encrypted wrapper storage;
- erase the credential and enter `REVOKED` after an explicit revocation response;
- treat a stale or rejected credential as a terminal authentication state, not a transient network
  error.

The Android runtime permission is a second enforcement point. For the initial profile this means
the notification permission for `notifications.send`; a denied or revoked permission returns a
structured local denial and performs no notification side effect. `device.status` remains
read-only and must not disclose secret material.

## M6 bridge handoff

The first integration path is an operator-managed, long-lived bridge process:

```text
Terminal 1:  hdp-bridge serve
Android:    ws://10.0.2.2:<configured-port>/hdp/v0/socket
Terminal 2:  hdp-bridge pair new
```

The emulator host route `10.0.2.2` is required for the first Android emulator gate. The bridge
must be running before pairing; the Android build stores the one-time credential returned by the
pairing handshake in protected storage. Restart the bridge and the Android process independently
to verify stable identity, credential reconnect, and full-set advertisement. Physical-device or
tunnel endpoints are separate evidence and must record TLS/tunnel and network assumptions.

This lifecycle is the reproducible M6 handoff, not the final product decision. Plugin autostart,
a systemd user unit, and Hermes-managed lifecycle remain open after M6. HDP remains the capability
transport; Hermes conversation and session access continue through Hermes's existing mobile
channel.

## Protocol conformance target

Conformance tests must connect to an endpoint and assert frames, payloads, state transitions, and
structured outcomes only. They must not import Android classes, Python reference-node handlers,
or depend on CLI output. The M5 Android-shaped fixture in `tests/conformance/` follows this same
boundary and is only a protocol test double; it is not Android lifecycle evidence.

The target rows are:

| Area | Observable assertion |
|---|---|
| handshake | `hello`/`welcome` negotiates HDP/0; unsupported versions fail closed |
| identity/auth | pairing issues one credential; reconnect keeps the same `device_id`; rejected/revoked credentials stop retrying |
| advertisement | initial and later capability lists are full-set, atomic replacements |
| invocation | allowed minimal capabilities ack, execute, validate, and return schema-valid results |
| local policy | unsupported/sensitive capabilities return structured denial and cause no side effect |
| cancellation | cancellation prevents execution or suppresses a late result |
| lifecycle | disconnect/reconnect reuses identity, resets in-flight state, and applies bounded jittered backoff |
| revocation | `revoke` closes the session and prevents credential reconnect |

Passing these rows proves protocol compatibility. It does not prove Android UI, packaged APK,
Keystore behavior, runtime-permission prompts, OS notification delivery, emulator networking, or
device-farm behavior; those belong to the M6 evidence record.
