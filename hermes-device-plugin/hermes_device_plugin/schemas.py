"""LLM-facing tool schemas — plain dicts, imported by nothing else in this package.

Kept out of `tools.py` on purpose (design §5.3): a test can assert schema shape without pulling
in handler/runtime machinery, and at M1 these input shapes get mirrored into
`hdp-spec/capabilities/*.md` for FR-6's byte-identical conformance test. Each `"parameters"`
block is a standard JSON-Schema object, matching the shape Hermes's own built-in tools use
(e.g. `tools/focus_pane_tool.py`'s `FOCUS_PANE_SCHEMA`).
"""

from __future__ import annotations

NOTIFICATIONS_SEND = {
    "name": "device_notifications_send",
    "description": (
        "Send a notification (title + body) to a paired device. Proves the tool -> device "
        "action-routing path end to end; the M0/M1 reference node just prints it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Notification title."},
            "body": {"type": "string", "description": "Notification body text."},
            "device": {
                "type": "string",
                "description": (
                    "Optional device id to target. Omit to let HDP pick automatically when "
                    "exactly one online device advertises this capability."
                ),
            },
        },
        "required": ["title", "body"],
    },
}

STATUS_GET = {
    "name": "device_status_get",
    "description": (
        "Report paired devices, their online state, advertised capabilities, and bridge health. "
        "Always available, even when nothing else works — use this first to see what's "
        "connected, and again after any device_* error to check whether the target is online."
    ),
    "parameters": {"type": "object", "properties": {}},
}

ECHO = {
    "name": "hdp_echo",
    "description": (
        "Round-trip an arbitrary JSON payload to a paired device and back. Use this to tell "
        "apart 'the connection is dead' from 'a specific capability is broken' — if hdp_echo "
        "succeeds but another device_* tool fails, the wire is alive and the failure is "
        "elsewhere."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "payload": {"type": "object", "description": "Arbitrary JSON object to round-trip."},
            "device": {
                "type": "string",
                "description": "Optional device id to target. Omit to auto-select.",
            },
        },
        "required": ["payload"],
    },
}
