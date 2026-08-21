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
from hermes_device_plugin import runtime, tools
from hermes_device_plugin.runtime import get_runtime
from hermes_device_plugin.transport.base import BridgeStatus, CapabilityInfo, DeviceInfo

_HDP_THREAD_NAME = "hdp-runtime"


@pytest.fixture(autouse=True)
def _clean_runtime_singleton():
    """Every test starts and ends with no HDP thread alive, so leak assertions are meaningful
    and tests don't leak singleton state into each other."""
    yield
    with contextlib.suppress(Exception):
        get_runtime().close()
    get_runtime.reset()
    runtime._reset_availability_for_tests()


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


def test_capability_check_fns_default_visible_without_forcing_runtime_construction():
    """Unknown startup state is visible and a synchronous check never builds the runtime."""
    assert tools.notifications_available() is True
    assert tools.echo_available() is True
    assert _HDP_THREAD_NAME not in _thread_names()


def test_capability_availability_snapshot_is_thread_safe_and_capability_specific():
    notifications = DeviceInfo(
        device_id="dev-notify",
        friendly_name="phone",
        platform="android",
        online=True,
        capabilities=[CapabilityInfo(name="notifications.send", version=1)],
    )
    runtime._update_availability(BridgeStatus(healthy=True), [notifications])

    assert tools.notifications_available() is True
    assert tools.echo_available() is False

    barrier = threading.Barrier(9)

    def _read_snapshot() -> tuple[bool, bool]:
        barrier.wait()
        return tools.notifications_available(), tools.echo_available()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_read_snapshot) for _ in range(8)]
        barrier.wait()
        assert all(future.result(timeout=2) == (True, False) for future in futures)


def test_unhealthy_bridge_hides_both_capability_tools() -> None:
    runtime._update_availability(BridgeStatus(healthy=False), [])

    assert tools.notifications_available() is False
    assert tools.echo_available() is False


def test_runtime_refreshes_availability_after_transport_start(monkeypatch) -> None:
    class _Transport:
        def __init__(self) -> None:
            self.listed = threading.Event()

        async def start(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def status(self) -> BridgeStatus:
            return BridgeStatus(healthy=True)

        async def list_devices(self) -> list[DeviceInfo]:
            self.listed.set()
            return [
                DeviceInfo(
                    device_id="dev-echo",
                    friendly_name="echo-node",
                    platform="linux",
                    online=True,
                    capabilities=[CapabilityInfo(name="diagnostics.echo", version=1)],
                )
            ]

    transport = _Transport()
    monkeypatch.setattr(runtime, "SocketTransport", lambda: transport)

    instance = runtime.HDPRuntime()
    try:
        assert transport.listed.wait(timeout=2)
        assert tools.notifications_available() is False
        assert tools.echo_available() is True
    finally:
        instance.close()


def test_hung_availability_refresh_cannot_keep_runtime_thread_alive(monkeypatch) -> None:
    class _HungTransport:
        def __init__(self) -> None:
            self.status_started = threading.Event()

        async def start(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def status(self) -> BridgeStatus:
            self.status_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def list_devices(self) -> list[DeviceInfo]:
            raise AssertionError("status must time out before device listing")

    transport = _HungTransport()
    monkeypatch.setattr(runtime, "SocketTransport", lambda: transport)

    instance = runtime.HDPRuntime()
    assert transport.status_started.wait(timeout=2)

    instance.close(timeout=2)

    assert not instance._thread.is_alive()
    assert tools.notifications_available() is True
    assert tools.echo_available() is True


async def test_failed_availability_refresh_retains_last_snapshot() -> None:
    class _FailingTransport:
        async def status(self) -> BridgeStatus:
            raise OSError("bridge sample failed")

        async def list_devices(self) -> list[DeviceInfo]:
            raise AssertionError("list must not run after status failed")

    notification = DeviceInfo(
        device_id="dev-notify",
        friendly_name="phone",
        platform="android",
        online=True,
        capabilities=[CapabilityInfo(name="notifications.send", version=1)],
    )
    runtime._update_availability(BridgeStatus(healthy=True), [notification])
    instance = object.__new__(runtime.HDPRuntime)
    instance.transport = _FailingTransport()

    await instance._refresh_availability()

    assert tools.notifications_available() is True
    assert tools.echo_available() is False
