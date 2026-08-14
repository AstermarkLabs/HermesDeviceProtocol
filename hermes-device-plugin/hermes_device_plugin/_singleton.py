"""Stdlib fallback for `plugins.plugin_utils.lazy_singleton`, used only when no Hermes install is
on `sys.path` (bare `pytest` runs — see `runtime.py`'s import shim).

This must be a genuine double-checked-locking implementation, not a stub: `runtime.py`'s tests
hammer `get_runtime()` from concurrent threads specifically to prove the singleton race is
closed, and a fallback that races on that one path (the path tests actually exercise) would
defeat the entire point of the test (docs/m0-plan.md §6.2). Semantics are intentionally
identical to `plugins/plugin_utils.py:lazy_singleton` in the Hermes checkout — same
double-checked locking, same `.reset()` teardown hook — so switching between the two import
paths never changes behavior, only which process is doing the importing.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def lazy_singleton(factory: Callable[[], T]) -> Callable[[], T]:
    lock = threading.Lock()
    box: list[T] = []  # one-element [instance]; empty == not yet built

    @functools.wraps(factory)
    def accessor() -> T:
        if box:
            return box[0]
        with lock:
            if box:  # re-check inside the lock
                return box[0]
            instance = factory()
            box.append(instance)
            return instance

    def reset() -> None:
        with lock:
            box.clear()

    accessor.reset = reset  # type: ignore[attr-defined]
    return accessor
