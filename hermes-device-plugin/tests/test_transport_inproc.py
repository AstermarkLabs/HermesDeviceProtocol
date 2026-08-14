"""The M0 loopback stub in isolation — no server, no socket, no node (design §6.4)."""

from __future__ import annotations

from hermes_device_plugin.transport.base import InvokeRequest
from hermes_device_plugin.transport.inproc import InprocTransport


async def test_list_devices_is_empty_at_m0():
    transport = InprocTransport()
    assert await transport.list_devices() == []


async def test_status_reports_unstarted_before_start():
    transport = InprocTransport()
    status = await transport.status()
    assert status.healthy is False


async def test_status_reports_healthy_after_start():
    transport = InprocTransport()
    await transport.start()
    status = await transport.status()
    assert status.healthy is True
    await transport.close()


async def test_invoke_round_trips_through_the_real_codec_and_succeeds():
    transport = InprocTransport()
    await transport.start()
    request = InvokeRequest(
        capability="notifications.send",
        version=1,
        device_id=None,
        args={"title": "t", "body": "b"},
        deadline_ms=1000,
    )
    result = await transport.invoke(request)
    assert result.ok is True
    assert result.invocation_id  # a real ULID was minted
    await transport.close()
