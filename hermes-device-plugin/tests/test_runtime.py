"""The real M0 deliverable (docs/m0-plan.md §6.5): `HDPRuntime` called from all three
`_run_async` calling contexts — no loop, an already-running loop, and a worker thread — with one
shared instance and no leaked thread. This mirrors `model_tools._run_async`'s three branches
(`~/.hermes/hermes-agent/model_tools.py:103`) without needing a Hermes install.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import json
import threading

import pytest
from hermes_device_plugin import tools
from hermes_device_plugin.runtime import get_runtime

_HDP_THREAD_NAME = "hdp-runtime"


@pytest.fixture(autouse=True)
def _clean_runtime_singleton():
    """Every test starts and ends with no HDP thread alive, so leak assertions are meaningful
    and tests don't leak singleton state into each other."""
    yield
    with contextlib.suppress(Exception):
        get_runtime().close()
    get_runtime.reset()


def _thread_names() -> set[str]:
    return {t.name for t in threading.enumerate()}


def test_three_run_async_scenarios_share_one_runtime_and_leak_nothing():
    baseline = _thread_names()

    # Scenario A — CLI path: no loop running, `asyncio.run` creates one.
    result_a = asyncio.run(tools.device_status_get({}))
    assert json.loads(result_a)["ok"] is True
    runtime_a = get_runtime()

    # Scenario B — an already-running loop awaits the handler directly (the branch a disposable
    # thread + fresh loop serves in real `_run_async`, e.g. gateway mode).
    async def _await_inside_running_loop():
        return await tools.device_status_get({})

    result_b = asyncio.run(_await_inside_running_loop())
    assert json.loads(result_b)["ok"] is True
    runtime_b = get_runtime()

    # Scenario C — a worker thread with its own loop (parallel tool execution).
    def _call_from_worker_thread():
        return asyncio.run(tools.device_status_get({}))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        result_c = pool.submit(_call_from_worker_thread).result(timeout=10)
    assert json.loads(result_c)["ok"] is True
    runtime_c = get_runtime()

    # One shared HDPRuntime instance across all three calling contexts — never re-built.
    assert runtime_a is runtime_b is runtime_c

    # No thread leaked beyond the single named HDP thread.
    assert _thread_names() - baseline == {_HDP_THREAD_NAME}


def test_get_runtime_is_race_free_under_concurrent_first_calls():
    """The race `lazy_singleton` exists for: N threads calling `get_runtime()` cold, at once,
    must produce exactly one instance and exactly one HDP thread."""
    barrier = threading.Barrier(8)

    def _call():
        barrier.wait()
        return get_runtime()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _call(), range(8)))

    assert len({id(r) for r in results}) == 1
    assert sum(1 for t in threading.enumerate() if t.name == _HDP_THREAD_NAME) == 1


def test_runtime_healthy_does_not_force_construction():
    """D6: `check_fn` must never build the runtime as a side effect of a health read."""
    assert tools.runtime_healthy() is True
    assert _HDP_THREAD_NAME not in _thread_names()
