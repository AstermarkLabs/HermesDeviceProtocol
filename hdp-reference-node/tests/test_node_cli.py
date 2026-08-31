"""M4 reference-node CLI overrides used by the multi-node lifecycle harness."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from hdp_reference_node import cli, node
from hdp_reference_node.faults import FaultConfig


def test_pair_code_is_not_a_reference_node_option() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "connect",
                "--name",
                "node-a",
                "--pair-code",
                "PAIR",
            ]
        )


def test_capability_version_overrides_replace_only_named_capability_versions() -> None:
    descriptors = node.descriptors_for_overrides(["notifications.send@1", "notifications.send@2"])

    advertised = {(descriptor.name, descriptor.version) for descriptor in descriptors}
    assert advertised == {
        ("notifications.send", 1),
        ("notifications.send", 2),
        ("diagnostics.echo", 1),
        ("device.status", 1),
    }
    notification_descriptors = [
        descriptor for descriptor in descriptors if descriptor.name == "notifications.send"
    ]
    assert all(
        descriptor.input_schema == node._DESCRIPTORS[0].input_schema
        for descriptor in notification_descriptors
    )
    assert all(
        descriptor.output_schema == node._DESCRIPTORS[0].output_schema
        for descriptor in notification_descriptors
    )


@pytest.mark.parametrize(
    "overrides",
    [
        ["notifications.send"],
        ["@2"],
        ["notifications.send@"],
        ["notifications.send@two"],
        ["notifications.send@0"],
        ["notifications.send@-1"],
        ["unknown.capability@1"],
        ["notifications.send@2", "notifications.send@2"],
    ],
)
def test_capability_version_overrides_reject_invalid_values(overrides: list[str]) -> None:
    with pytest.raises(ValueError):
        node.descriptors_for_overrides(overrides)


def test_production_descriptors_remain_version_one_without_overrides() -> None:
    descriptors = node.descriptors_for_overrides([])

    assert descriptors == node._DESCRIPTORS
    assert {descriptor.version for descriptor in descriptors} == {1}


async def test_overridden_version_keeps_the_builtin_handler() -> None:
    descriptors = node.descriptors_for_overrides(["diagnostics.echo@7"])
    descriptor = next(item for item in descriptors if item.name == "diagnostics.echo")
    session = node._NodeSession(None, FaultConfig())  # type: ignore[arg-type]

    result = await session._build_result(descriptor.name, {"payload": {"version": 7}})

    assert descriptor.version == 7
    assert result.ok is True
    assert result.data == {"payload": {"version": 7}}


def test_explicit_credential_auth_failure_does_not_name_shared_file_for_deletion() -> None:
    with (
        patch.object(cli.node, "run", return_value=object()),
        patch.object(cli.asyncio, "run", side_effect=node.AuthFailed("credential rejected")),
        pytest.raises(SystemExit) as raised,
    ):
        cli.main(
            [
                "connect",
                "--name",
                "second-node",
                "--url",
                "ws://127.0.0.1:1/hdp/v0/socket",
                "--credential",
                "second-node-secret",
                "--credential-file",
                "/shared/default-credential",
            ]
        )

    message = str(raised.value)
    assert "--credential" in message
    assert "/shared/default-credential" not in message
    assert "remov" not in message.lower()
