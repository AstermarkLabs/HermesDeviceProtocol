# `notifications.send@1`

Sends a title/body notification to the device. The M1 reference node's implementation simply
prints the title and body to stdout — this capability proves the tool → device action-routing
path end to end, not any particular notification UI.

## Input schema

Byte-identical to `hermes_device_plugin/schemas.py`'s `NOTIFICATIONS_SEND["parameters"]`, minus
the `device` field (routing which device to target is a plugin/tool-level concern — the node
never sees it, since `corr`/dispatch already resolved a specific connection by the time `invoke`
reaches the node).

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string", "description": "Notification title."},
    "body": {"type": "string", "description": "Notification body text."}
  },
  "required": ["title", "body"]
}
```

## Output schema

```json
{
  "type": "object",
  "properties": {
    "delivered": {"type": "boolean"}
  },
  "required": ["delivered"]
}
```

## Semantics

Fire-and-forget from the model's point of view: a successful result means the node accepted and
displayed (at M1: printed) the notification, not that a human read it. `delivered` is always
`true` on success — there is no read-receipt in the MVP.

## Versioning (FR-10)

Adding an optional input field (e.g. a future `priority`) does not bump the version. Changing
`title`/`body` to optional, removing either, or changing the output shape requires a version
bump to `notifications.send@2`.
