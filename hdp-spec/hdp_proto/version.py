"""HDP wire version and the known-message-type boundary.

The full HDP/0 type set, per `hdp-spec/HDP-0.md` §2: Node→Bridge (`hello`, `capabilities`,
`ack`, `result`, `progress`, `heartbeat`, `error`) and Bridge→Node (`welcome`, `invoke`, `cancel`,
`ack`, `revoke`, `heartbeat`, `error`), deduplicated into one set — the same envelope and type
names are reused for the plugin↔bridge control plane too (ADR-0004), so a single receiver-side
set covers both directions and both planes.

The boundary this module exists to state: a receiver rejects an unknown *type* with an `error`
reply (or refuses the connection, for the version itself); it must never reject an unknown
*field* within a known type. That second half lives in `envelope.py`'s `from_wire`.
"""

from __future__ import annotations

HDP_VERSION = "0"
"""The literal value of the envelope's `hdp` field. A different value is a rejection, not a
best-effort parse — see envelope.py `from_wire`."""

NODE_TYPES = frozenset(
    {
        "hello",
        "welcome",
        "capabilities",
        "invoke",
        "cancel",
        "ack",
        "result",
        "progress",
        "revoke",
        "heartbeat",
        "error",
    }
)
"""The full HDP/0 node-facing message-type set (hdp-spec/HDP-0.md §2). `progress` and `revoke`
are declared but have no producer or consumer at M1 — see HDP-0.md §2's note on why they're
defined early."""

CONTROL_TYPES = frozenset(
    {
        # Plugin-reachable (the only ones `hermes_device_plugin`'s `transport/socket.py` sends).
        "ctl_invoke",
        "ctl_invoke_reply",
        "ctl_cancel",
        "ctl_cancel_reply",
        "ctl_list_devices",
        "ctl_list_devices_reply",
        "ctl_status",
        "ctl_status_reply",
        "ctl_list_approvals",
        "ctl_list_approvals_reply",
        "ctl_resolve_approval",
        "ctl_resolve_approval_reply",
        # Operator-only (only `hdp-bridge`'s own CLI sends these).
        "ctl_devices_revoke",
        "ctl_devices_revoke_reply",
        "ctl_devices_list_detailed",
        "ctl_devices_list_detailed_reply",
        "ctl_audit_tail",
        "ctl_audit_tail_reply",
        "ctl_policy_show",
        "ctl_policy_show_reply",
        "ctl_policy_reload",
        "ctl_policy_reload_reply",
        # Always rejected with `auth_failed`, from any connection (control.py's `_REJECTED_VERBS`)
        # — still a *known* type so the rejection happens at the dispatch layer where it can be
        # audited, not silently at the codec layer as an unparseable frame.
        "ctl_policy_set",
        "ctl_pair_mint",
    }
)
"""The plugin↔bridge Unix-socket control-plane type vocabulary (ADR-0004, this plan's Global
Constraints — the "Control-plane verb set" note pins these exact strings). `hdp_bridge/control.py`
dispatches on this set separately from `NODE_TYPES`; adding a string here does not add a handler —
Task 6 onward lands the handlers for the verbs pinned but not yet implemented, which today hit
`control.py`'s `NOT_IMPLEMENTED` fallback rather than being rejected as an unparseable envelope."""

KNOWN_TYPES = NODE_TYPES | CONTROL_TYPES
"""The full set `Envelope.from_wire` accepts, across both planes it serves (ADR-0004: "same
envelope, same type names" is reused for the private control-plane vocabulary too, so a single
receiver-side set covers both directions and both planes). Per-plane direction/legality checks
still live where they always did: `connection.py`'s `_NODE_TO_BRIDGE_TYPES` for the node socket,
`control.py`'s dispatch map and `_REJECTED_VERBS` for the control socket."""
