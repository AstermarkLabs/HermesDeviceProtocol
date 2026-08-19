"""Protocol-level observability for frames received by the reference node."""

from __future__ import annotations

import json
import logging

import pytest
from hdp_proto.envelope import Envelope
from hdp_reference_node.faults import FaultConfig
from hdp_reference_node.node import _NodeSession


class _WebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, value: str) -> None:
        self.sent.append(value)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_invoke_frame_is_logged_before_dispatch(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="hdp_reference_node.node")
    session = _NodeSession(_WebSocket(), FaultConfig())  # type: ignore[arg-type]
    invoke = Envelope.new(
        "invoke",
        {
            "capability": "diagnostics.echo",
            "version": 1,
            "args": {"payload": {"probe": True}},
            "deadline_ms": 1_000,
        },
        corr="01K123456789ABCDEFGHJKMNPQ",
    )

    await session.handle_frame(json.dumps(invoke.to_wire()))

    assert (
        "received invoke invocation_id=01K123456789ABCDEFGHJKMNPQ "
        "capability=diagnostics.echo version=1"
    ) in caplog.text
