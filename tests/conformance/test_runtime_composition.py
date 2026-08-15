"""M1-1's risk mitigation (m1-plan.md §9): the embedded aiohttp server's start/stop lifecycle,
owned by `HDPRuntime` (not module import), must not leak file descriptors, ports, or threads
across repeated start/stop cycles — this is what happens every time a long-lived host process
restarts the plugin's runtime.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest
from hermes_device_plugin.runtime import HDPRuntime

_HDP_THREAD_NAME = "hdp-runtime"


def _fd_count() -> int:
    return len(os.listdir(f"/proc/{os.getpid()}/fd"))


def _hdp_thread_count() -> int:
    return sum(1 for t in threading.enumerate() if t.name == _HDP_THREAD_NAME)


def _wait_for_no_hdp_threads(*, timeout_s: float = 10.0) -> None:
    """`HDPRuntime.close()` already blocks on `Thread.join()`, but the loop thread only notices
    the `_close_requested` flag on its next 50ms poll and then still has to tear the transport
    down — under a loaded test suite that can occasionally outlast the join's own timeout. This
    settles before the fd count is measured, so a merely-slow-to-finish thread from one cycle
    doesn't read as a leak, and doesn't bleed a stray thread into whichever test runs next."""
    deadline = time.monotonic() + timeout_s
    while _hdp_thread_count() > 0 and time.monotonic() < deadline:
        time.sleep(0.05)


@pytest.mark.skipif(sys.platform != "linux", reason="fd counting via /proc is Linux-specific")
@pytest.mark.timeout(30)
def test_repeated_runtime_start_stop_does_not_leak_fds_or_threads():
    baseline = _fd_count()
    for _ in range(10):
        runtime = HDPRuntime()
        runtime.close()
        _wait_for_no_hdp_threads()

    assert _hdp_thread_count() == 0
    # Slack rather than an exact match: neither the OS nor pytest's own fd usage is perfectly
    # deterministic run to run. What matters is there is no unbounded growth — ten genuinely
    # leaked sockets would blow well past a slack of a handful.
    assert _fd_count() <= baseline + 5
