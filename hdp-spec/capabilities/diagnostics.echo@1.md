# `diagnostics.echo@1`

Round-trips an arbitrary JSON object through the node and back unchanged. Used to tell apart "the
wire is dead" from "a specific capability is broken" — if `hdp_echo` succeeds but another
`device_*` tool fails, the wire is alive and the failure is elsewhere.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "payload": {"type": "object", "description": "Arbitrary JSON object to round-trip."}
  },
  "required": ["payload"]
}
```

## Output schema

```json
{
  "type": "object",
  "properties": {
    "payload": {"type": "object", "description": "The same object the caller sent."}
  },
  "required": ["payload"]
}
```

## Semantics

The node's handler returns `payload` unmodified. `output.payload` must be deep-equal to
`input.payload` for a well-behaved node; a node under the `malformed-result` or `stale-schema`
fault flags (see `hdp-reference-node`'s `faults.py`) may deliberately violate this to exercise
the conformance suite's failure paths.

## Versioning (FR-10)

`payload`'s type is deliberately unconstrained (`object`, no nested schema) — there is no
narrower shape to add optional fields to. A version bump would only be needed if the capability
stopped being a pure round-trip.
