"""The node-side second enforcement point (docs/design.md §4). Trivial at M1: every capability
this node implements is allowed — there is no per-capability or per-caller distinction yet. This
exists as a real decision point (a function with a real call site in `node.py`) rather than being
invented later, so a subsequent milestone — or the M5 Android node — has a call site to fill
instead of a stub to write from scratch.
"""

from __future__ import annotations

_ALLOWED = frozenset({"notifications.send", "diagnostics.echo", "device.status"})


def is_allowed(capability: str) -> bool:
    return capability in _ALLOWED
