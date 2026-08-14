"""FR-1: every handler returns parseable JSON and never propagates an exception, including on
injected internal failure. Two injection points, both required (docs/m0-plan.md §5.6): a failure
inside `engine.invoke` arrives through `wrap_future` as an exception on the caller's loop; a
failure in `get_runtime()` happens before any future exists, on a different code path.
"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import patch

import pytest
from hdp_proto.errors import ErrorCode
from hermes_device_plugin import engine, tools
from hermes_device_plugin.runtime import get_runtime

_KNOWN_CODES = {c.value for c in ErrorCode}


@pytest.fixture(autouse=True)
def _clean_runtime_singleton():
    yield
    with contextlib.suppress(Exception):
        get_runtime().close()
    get_runtime.reset()


def _assert_structured_failure(raw: str) -> None:
    assert isinstance(raw, str)
    parsed = json.loads(raw)
    assert parsed["ok"] is False
    assert parsed["error"]["code"] in _KNOWN_CODES
    assert parsed["error"]["hint"]


@pytest.mark.parametrize(
    ("handler_name", "args"),
    [
        ("device_notifications_send", {"title": "t", "body": "b"}),
        ("hdp_echo", {"payload": {}}),
    ],
)
async def test_handler_survives_engine_invoke_raising(handler_name, args):
    handler = getattr(tools, handler_name)
    with patch.object(engine, "invoke", side_effect=RuntimeError("boom")):
        result = await handler(args)
    _assert_structured_failure(result)


@pytest.mark.parametrize(
    ("handler_name", "args"),
    [
        ("device_notifications_send", {"title": "t", "body": "b"}),
        ("device_status_get", {}),
        ("hdp_echo", {"payload": {}}),
    ],
)
async def test_handler_survives_get_runtime_raising(handler_name, args):
    handler = getattr(tools, handler_name)
    with patch("hermes_device_plugin.tools.get_runtime", side_effect=RuntimeError("boom")):
        result = await handler(args)
    _assert_structured_failure(result)


async def test_device_status_get_survives_internal_failure():
    """`device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable point is
    `_status_get_body`, the equivalent boundary for this one handler."""
    with patch.object(tools, "_status_get_body", side_effect=RuntimeError("boom")):
        result = await tools.device_status_get({})
    _assert_structured_failure(result)


async def test_device_status_get_succeeds_with_zero_nodes():
    """FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}` with the real
    (unmocked) loopback stub — an empty device list is success, not an error, and this is the
    tool that must stay visible when nothing else works."""
    result = json.loads(await tools.device_status_get({}))
    assert result == {"ok": True, "data": {"devices": []}}
