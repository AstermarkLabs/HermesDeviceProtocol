# `device.status@1`

Reports node-local liveness information. **This capability is deliberately not what the
`device_status_get` plugin tool calls** — that tool reports bridge-side registry state
(`runtime.transport.list_devices()`) and does not invoke any capability over the wire, at M1 or
otherwise. `device.status@1` exists so the capability itself — the same kind of thing a real node
would advertise, dispatch, and answer — is exercised end to end by the conformance suite,
independent of the tool that happens to share a name with it.

This decision was confirmed explicitly during M1 planning: the docs do not describe
`device_status_get` routing through `engine.invoke()`, and rewiring it to do so was out of scope
for M1.

## Input schema

No input.

```json
{"type": "object", "properties": {}}
```

## Output schema

```json
{
  "type": "object",
  "properties": {
    "platform": {"type": "string", "description": "Node-reported platform identifier, e.g. \"linux\", \"android\"."},
    "uptime_s": {"type": "number", "description": "Seconds since the node process started."}
  },
  "required": ["platform", "uptime_s"]
}
```

## Semantics

Purely informational and node-local — it does not reflect bridge-side registry state, pairing
state, or anything the bridge itself knows without asking. A conformance test invokes this
capability directly against the reference node and checks the output schema matches this
document byte-for-byte (FR-6); no plugin tool at M1 exercises this path as part of normal
operation.

## Versioning (FR-10)

Adding an optional output field (e.g. a future `battery_pct`) does not bump the version. Making
either existing field optional, removing one, or changing its type requires
`device.status@2`.
