"""`InvocationsMem` in isolation — no server, no socket, no node."""

from __future__ import annotations

import pytest
from hdp_bridge.invocations import DeviceDisconnected, InvocationsMem, PendingInvocation


async def test_mint_for_registers_a_pending_entry_and_is_pending():
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_01", capability="notifications.send")
    assert isinstance(entry, PendingInvocation)
    assert entry.device_id == "dev_01"
    assert entry.capability == "notifications.send"
    assert invocations.is_pending(invocation_id) is True
    assert len(invocations) == 1


async def test_mark_acked_resolves_the_ack_future_once():
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_01")
    assert invocations.mark_acked(invocation_id) is True
    assert entry.ack_future.done()
    # A second ack for the same id is a silent no-op, not an error.
    assert invocations.mark_acked(invocation_id) is False


async def test_mark_acked_on_unknown_id_returns_false():
    invocations = InvocationsMem()
    assert invocations.mark_acked("unknown") is False


async def test_resolve_pops_the_entry_and_sets_the_result_future():
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_01")
    invocations.mark_acked(invocation_id)
    assert invocations.resolve(invocation_id, {"ok": True}) is True
    assert entry.result_future.done()
    assert await entry.result_future == {"ok": True}
    assert invocations.is_pending(invocation_id) is False
    assert len(invocations) == 0


async def test_resolve_on_unknown_id_returns_false():
    invocations = InvocationsMem()
    assert invocations.resolve("unknown", {}) is False


async def test_expire_removes_without_touching_futures():
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_01")
    removed = invocations.expire(invocation_id)
    assert removed is entry
    assert invocations.is_pending(invocation_id) is False
    assert not entry.ack_future.done()
    assert not entry.result_future.done()


async def test_expire_on_unknown_id_returns_none():
    invocations = InvocationsMem()
    assert invocations.expire("unknown") is None


async def test_fail_all_for_device_fails_only_that_devices_entries():
    invocations = InvocationsMem()
    id_a, entry_a = invocations.mint_for("dev_a")
    id_b, entry_b = invocations.mint_for("dev_b")

    failed = invocations.fail_all_for_device("dev_a")

    assert failed == [id_a]
    assert invocations.is_pending(id_a) is False
    assert invocations.is_pending(id_b) is True
    with pytest.raises(DeviceDisconnected):
        await entry_a.ack_future
    assert not entry_b.ack_future.done()


async def test_fail_all_for_device_fails_result_future_when_already_acked():
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_a")
    invocations.mark_acked(invocation_id)

    invocations.fail_all_for_device("dev_a")

    assert entry.ack_future.done()
    assert not entry.ack_future.exception()
    with pytest.raises(DeviceDisconnected):
        await entry.result_future


async def test_fail_all_for_device_with_reason_revoked_sets_it_on_the_exception():
    """Default `fail_both=False` behavior — only the not-yet-done ack future gets the exception
    (the pre-existing anti-noise `elif`), just with a `"revoked"` reason instead of the default."""
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_a")

    failed = invocations.fail_all_for_device("dev_a", reason="revoked")

    assert failed == [invocation_id]
    with pytest.raises(DeviceDisconnected) as exc_info:
        await entry.ack_future
    assert exc_info.value.reason == "revoked"
    assert not entry.result_future.done()


async def test_fail_all_for_device_fail_both_sets_the_exception_on_both_futures():
    """`fail_both=True` — the opt-in `revoke_device`'s explicit step 4 uses, so a caller
    inspecting either future directly (not just through a sequential ack->result awaiter) observes
    the failure regardless of which one it looks at."""
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_a")

    failed = invocations.fail_all_for_device("dev_a", reason="revoked", fail_both=True)

    assert failed == [invocation_id]
    with pytest.raises(DeviceDisconnected) as exc_info:
        await entry.ack_future
    assert exc_info.value.reason == "revoked"
    with pytest.raises(DeviceDisconnected) as exc_info:
        await entry.result_future
    assert exc_info.value.reason == "revoked"


async def test_fail_all_for_device_default_reason_is_device_offline():
    invocations = InvocationsMem()
    invocation_id, entry = invocations.mint_for("dev_a")

    invocations.fail_all_for_device("dev_a")

    with pytest.raises(DeviceDisconnected) as exc_info:
        await entry.ack_future
    assert exc_info.value.reason == "device_offline"


async def test_fail_all_fails_every_pending_invocation_regardless_of_device():
    invocations = InvocationsMem()
    id_a, entry_a = invocations.mint_for("dev_a")
    id_b, entry_b = invocations.mint_for("dev_b")

    failed = invocations.fail_all()

    assert set(failed) == {id_a, id_b}
    assert len(invocations) == 0
    with pytest.raises(DeviceDisconnected):
        await entry_a.ack_future
    with pytest.raises(DeviceDisconnected):
        await entry_b.ack_future
