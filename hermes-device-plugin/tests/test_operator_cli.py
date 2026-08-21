from __future__ import annotations

import pytest
from hermes_device_plugin import cli


def test_approval_scope_is_constrained_by_parser():
    parser = cli._build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["approvals", "approve", "inv_1", "--scope", "invalid"])


async def test_approval_error_is_not_rendered_as_success(monkeypatch):
    class _Transport:
        async def start(self):
            return None

        async def close(self):
            return None

        async def resolve_approval(self, invocation_id, decision, scope):
            raise RuntimeError("approval is no longer pending")

    monkeypatch.setattr("hermes_device_plugin.transport.socket.SocketTransport", _Transport)

    with pytest.raises(RuntimeError, match="no longer pending"):
        await cli.resolve_approval("inv_1", "approve", "session")
