from __future__ import annotations

import pytest
from hdp_bridge import policy


@pytest.mark.parametrize(
    ("device_id", "capability", "expected_mode", "expected_source"),
    [
        ("dev_alpha", "notifications.send", "device", "device_capability"),
        ("dev_alpha", "diagnostics.echo", "ask", "device_default"),
        ("dev_beta", "notifications.send", "ask", "global_default"),
        ("dev_beta", "clipboard.read", "deny", "fallback"),
    ],
)
def test_resolve_uses_the_documented_precedence_and_fails_closed(
    device_id, capability, expected_mode, expected_source
):
    """Removing any resolution layer or changing the fallback to allow must fail this test."""
    table = policy.PolicyTable.from_data(
        {
            "version": 1,
            "defaults": {"notifications.send": "ask"},
            "devices": {
                "dev_alpha": {
                    "default": "ask",
                    "notifications.send": "device",
                }
            },
        },
        policy_seq=7,
    )

    decision = table.resolve(device_id, capability)

    assert decision.mode.value == expected_mode
    assert decision.source == expected_source
    assert decision.policy_seq == 7
