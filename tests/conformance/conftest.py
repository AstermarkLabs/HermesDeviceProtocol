"""Shared fixtures for the M1 conformance suite (m1-plan.md §7).

Each test starts a real `EmbeddedTransport` bound to an OS-assigned ephemeral TCP port and, where
a fault needs a real uncooperative peer, launches the real `hdp-node` CLI as a genuine subprocess
against it — proving the failure paths hold over an actual socket to a separate OS process
(m1-plan.md's header risk statement), not an in-process function call standing in for one.
"""

from __future__ import annotations

import pytest
from hermes_device_plugin import config
from hermes_device_plugin.transport.embedded import EmbeddedTransport


@pytest.fixture(autouse=True)
def _hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HDP_BIND_PORT", "0")
    yield tmp_path


@pytest.fixture
async def bridge():
    transport = EmbeddedTransport()
    await transport.start()
    try:
        yield transport
    finally:
        await transport.close()


@pytest.fixture
def bridge_url(bridge):
    host_port = config.bridge_addr_path().read_text().strip()
    return f"ws://{host_port}/hdp/v0/socket"
