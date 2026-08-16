# HDP/0 — Hermes Device Protocol, version 0

Normative wire-format specification. `hdp_proto` is its executable copy; where the two disagree,
this document wins and `hdp_proto` has a bug. Source planning document: `docs/m1-plan.md`.

## 1. The envelope

Every HDP message, in both directions and on both the node↔bridge and plugin↔bridge control
planes, is a single JSON object with exactly these fields:

```json
{"hdp": "0", "type": "invoke", "id": "01JB...", "ts": 1736200000000, "corr": "01JB...", "payload": {}}
```

| Field | Meaning |
|---|---|
| `hdp` | Protocol version string. `"0"` for this document. |
| `type` | Message type — see §2. |
| `id` | A ULID minted by the sender of *this* message. Doubles as an idempotency key: a receiver that sees a repeated `id` inside its dedupe window does not re-execute the message (FR-34). This is the second line of defense behind the pending-table check for duplicate results. |
| `ts` | Milliseconds since the Unix epoch, sender's clock, informational only — never used for ordering or idempotency (that's `id`'s job). |
| `corr` | The `invocation_id` this message correlates to, or `null` for messages with no invocation context (`hello`, `welcome`, `capabilities`, `heartbeat`). **Always minted by the bridge** (FR-28) — never by the plugin, never by the node. |
| `payload` | Type-specific body, an object (possibly empty). |

Rules:

- **Unknown fields are tolerated, not rejected.** This is normative, not merely a test's opinion —
  it is what lets a later milestone add fields to `hello` (or any other type) without breaking an
  M1 node. A receiver ignores fields it does not recognize.
- **Unknown message `type`s get an `error` reply; the connection stays open.** A malformed-frame
  counter tracks these per connection — see §5.
- **Hermes `task_id` / `session_id` ride in `payload` metadata only, never as envelope fields.**
  HDP correctness never depends on Hermes internals — the protocol works with those fields absent
  entirely.
- **`risk_class`** may be carried inside an `invoke` payload and is **reserved** — consulted
  nowhere in the MVP (M0–M4). It exists so a later milestone can wire policy to it without a wire
  break.

## 2. Message types

| Node → Bridge | Bridge → Node |
|---|---|
| `hello` | `welcome` |
| `capabilities` | `invoke` |
| `ack` | `cancel` |
| `result` | `ack` |
| `progress` | `revoke` |
| `heartbeat` | `heartbeat` |
| `error` | `error` |

The plugin↔bridge control plane reuses **the same envelope shape and the same type names** —
in-process at M0/M1, a Unix socket at M2 (ADR-0004). That identity is what makes the M2 extraction
a transport swap rather than a protocol rewrite.

`capabilities` is a **full-set replacement, never a delta** (FR-8): every `capabilities` message
lists the complete current set of capabilities the sender advertises, superseding whatever was
advertised before. This document defines that semantic at M1; the mid-session atomic-swap
behavior it implies is exercised by a conformance test at M4, not M1.

`progress` and `revoke` are defined here and unused at M1 (`progress` has no M1 producer or
consumer; `revoke` is unused until M2's credential-revocation work). Declaring them now keeps
their eventual use additive rather than a wire break.

## 3. Handshake

1. The node opens a WebSocket to `GET /hdp/v0/socket` and sends `hello` as its first frame:
   ```json
   {"hdp": "0", "type": "hello", "id": "...", "ts": ..., "corr": null,
    "payload": {"hdp_versions": [0], "device_name": "workshop-node",
                "capabilities": [...], "credential": null}}
   ```
   - `hdp_versions`: protocol versions the node speaks, in preference order.
   - `device_name`: a human-readable label, not an identifier.
   - `capabilities`: the node's initial full-set capability list (see §2's full-replacement rule
     and §6 for the descriptor shape) — `hello` doubles as the first `capabilities` message so a
     node need not send both.
   - `credential`: reserved for M2's pairing/auth. **At M1 the bridge accepts any value,
     including absent, and performs no verification.** The field exists on the wire from M1 so M2
     is an addition, not a break.
2. The bridge validates `hdp_versions` against its own supported set.
   - **On mismatch, the bridge closes the connection immediately — before reading, parsing, or
     logging `credential` or any other `hello` field.** A version we do not speak gets no auth
     processing at all.
   - On match, the bridge assigns a `device_id`, registers the node's capabilities, and replies
     `welcome`:
     ```json
     {"hdp": "0", "type": "welcome", "id": "...", "ts": ..., "corr": null,
      "payload": {"hdp_version": 0, "device_id": "01JB..."}}
     ```
3. Any frame other than `hello` sent before `welcome` is a protocol violation handled as an
   unknown/out-of-sequence frame per §5 (the connection is young enough that closing it is also an
   acceptable response — implementations may choose either as long as no invocation state is ever
   created before `welcome`).

`capabilities` sent after the handshake (mid-session) replaces the full set exactly as `hello`'s
initial set did.

## 4. Transport rules

These exist because the eventual deployment is a public hostname behind a tunnel, not a bare LAN.
Retrofitting them after M1 ships means changing a shipped protocol, so they land now even though
the tunnel itself is not part of the MVP:

- **WebSocket ping/pong every 15 seconds.** Implemented via the WS layer's built-in
  heartbeat/pong mechanism (e.g. aiohttp's `heartbeat=` parameter), not a hand-rolled
  application-level ping. Idle connections through a tunnel are dropped without this.
- **No reliance on client IP** for identity, rate limiting, or logging decisions.
- **`X-Forwarded-*` headers are untrusted input.** They may be parsed for diagnostics; they are
  never used in an authorization decision.
- **Unexpected/proxy-injected headers are tolerated.** An unrecognized header never fails a
  connection.
- **The bind address is a config value.** Binding to a non-loopback address requires the
  `HDP_ALLOW_REMOTE=1` environment variable; absent that, a non-loopback bind attempt returns
  `not_implemented` rather than binding (NFR-4). The guard ships at M1; the remote-bind capability
  itself does not.

## 5. Malformed and out-of-sequence frames

A frame that parses as JSON but has an unrecognized `type`, or fails envelope validation in a way
that is not a version mismatch, gets an `error` reply and the connection **stays open**. Each
connection tracks a sliding 60-second window of such malformed frames; **10 malformed frames
within that window closes the connection.** This bounds the cost of a confused or hostile peer
without punishing a single transient bad frame.

A **protocol-version mismatch is different**: it closes the connection immediately (§3), with no
`error` reply and no credential processing, because a peer speaking a version we don't support may
not even be able to parse our `error` envelope correctly.

## 6. Capability descriptors

Each entry in a `capabilities` message (and in `hello.payload.capabilities`) has the shape:

```json
{"name": "notifications.send", "version": 1, "input_schema": {...}, "output_schema": {...}}
```

`input_schema` and `output_schema` are JSON Schema objects. **Versioning rule (FR-10):** adding an
*optional* input field does not bump `version`. Changing a required input, removing a field, or
changing the output shape does. See `hdp-spec/capabilities/*.md` for the three MVP capabilities'
normative schemas — a conformance test asserts the reference node's advertised schema is
byte-identical to the schema documented there (FR-6).

## 7. Invocation lifecycle

```
invoke ──→ [ack timeout 5s] ──→ acked ──→ [execution deadline] ──→ result
   │                              │                                  │
   └─→ device_offline             └─→ invocation_timeout             └─→ validate output schema
                                                                          │
                                                           malformed_result ←┘ (on failure)
```

- **`invoke`** (bridge → node): `payload` carries `capability`, `version`, `args`, and
  `deadline_ms` (the execution deadline, milliseconds from when the node acks). `corr` is the
  bridge-minted `invocation_id`.
- **`ack`** (node → bridge): the node's receipt of `invoke`, correlated by `corr`. Ack timeout is
  **5 seconds, strictly less than the execution deadline** — a node that never acks fails fast
  (`device_offline`) rather than burning the full deadline.
- **`result`** (node → bridge): `payload` carries `ok` and either `data` or an error shape,
  correlated by `corr`. Validated against the capability's output schema before being trusted;
  failure is `malformed_result` (and, if the cause is schema drift specifically, a paired
  log-only `schema_drift` record).
- **`cancel`** (bridge → node): sent best-effort on timeout or explicit cancellation. **The
  pending-table entry is removed first, then `cancel` is sent** — reversing this order leaks an
  entry whenever the send itself fails. A node need not honor `cancel`; whichever of `cancel` or
  a late `result` reaches a terminal pending-table entry first wins, and the other is a no-op.
- **Late results.** A `result` whose `corr` is not in the pending table (already resolved, timed
  out, or cancelled) is **dropped silently** on the plugin/model-facing side and **logged as
  `late_result`** on the bridge side.
- **Mid-call disconnect.** If a node's connection closes or its heartbeat is missed while
  invocations are in flight for it, **all of that device's in-flight invocations fail
  immediately** with `device_offline` — implementations must not wait for the deadline to elapse
  when the answer (the device is gone) is already known.

Two invariants hold across every path above, and are asserted in every failure-path test's
teardown:

- **Nothing hangs.** Every path terminates within `deadline_ms + ε`.
- **Nothing leaks.** After any terminal outcome, the `invocation_id` is absent from both the
  plugin's pending table and the bridge's invocation table.

## 8. HTTP surface

| Route | M1 behavior |
|---|---|
| `GET /hdp/v0/health` | Live. Returns `200 {"status": "ok"}`. |
| `GET /hdp/v0/socket` | WebSocket upgrade; see §3. |
| `POST /hdp/v0/pair` | **Absent at M1** — no route registered (404). Added at M2. |
| `/hdp/v0/blobs` (any method) | **Reserved.** Returns `501`. |

**Binary payload rule, normative from day one:** metadata travels in the JSON envelope; binary
payloads travel over HTTP by content ID; **base64-encoded binary inside an envelope is
forbidden.** Roughly twenty lines of cost now, versus a protocol break the first time something
needs to send a screenshot.

## 9. Errors

See `hdp-spec/errors.md` for the closed error-code taxonomy. Error frames on the wire use
`type: "error"` with `payload` shaped `{"code", "message", "hint"}` — the same shape
`hdp_proto.errors.err()` produces for the model-facing result envelope, so a bridge translating a
wire-level `error` frame into a tool result does not need to reshape it.

## Amendments (v0.2)

Landed at M2, without a wire break (§3's "unknown fields tolerated" rule is what makes this
possible — see docs/m2-plan.md §4.3). The `hdp` envelope field's value is unchanged (`"0"`); this
is a document revision, not a new protocol version.

- **`hello.credential` is now verified.** M1 accepted any value, including absent. M2 requires a
  credential: either an existing device's stored credential (a returning connection), or a
  first-time pairing code prefixed `pair:` (a new pairing). Absent or invalid → `auth_failed`,
  connection closed. There is no more anonymous/unpaired connection path.
- **`welcome.credential`** (new, optional field): present only on a first-time pairing
  handshake, carrying the newly-issued device credential in plaintext exactly once (FR-12).
  Absent on every other `welcome`.
- **`revoke` is now sent** by the bridge on operator-initiated revocation (§4.4).
- **`POST /hdp/v0/pair` remains absent on the HTTP surface** — M2 implements pairing entirely
  through the WebSocket handshake's `pair:`-prefixed credential, not a separate REST endpoint.
  (Deliberate deviation from m2-plan.md's mention of a `POST /hdp/v0/pair` route: a second HTTP
  round trip before the WebSocket upgrade would need its own auth story for no benefit, since the
  pairing code itself is already the one-time secret. Recorded here as the resolution of that
  ambiguity, not a silent drop.)
