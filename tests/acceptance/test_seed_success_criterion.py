"""M4 acceptance: seed architecture success criterion, clause by clause."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import TypeVar

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HERMES_COMMIT = "069551d19bc572744ed570dc51b82ee4b0efb6c8"
_HERMES_VERSION = "v0.20.0"
_HERMES_PYTHON = "3.11.15"
_T = TypeVar("_T")


def _parse_session_id(stderr: str) -> str:
    match = re.search(r"(?m)^session_id:\s*(\S+)\s*$", stderr)
    if match is None:
        raise AssertionError(f"Hermes quiet-mode stderr did not contain a session id:\n{stderr}")
    return match.group(1)


def _parse_install_directory(version_output: str) -> Path:
    match = re.search(r"(?m)^Install directory:\s*(.+?)\s*$", version_output)
    if match is None:
        raise AssertionError(
            f"hermes --version did not report an Install directory:\n{version_output}"
        )
    return Path(match.group(1)).expanduser().resolve()


def _parse_pending_invocation_id(output: str) -> str | None:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        for approval in parsed:
            if isinstance(approval, dict) and isinstance(approval.get("invocation_id"), str):
                return approval["invocation_id"]
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) >= 5 and "@" in fields[2] and fields[0]:
            return fields[0]
    return None


def _device_tool_count(output: str) -> int:
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"hermes prompt-size did not return JSON:\n{output}") from exc
    for row in data.get("toolsets_breakdown", []):
        if row.get("toolset") == "device":
            count = row.get("tool_count")
            if isinstance(count, int):
                return count
    raise AssertionError(f"Hermes did not expose a device toolset:\n{output}")


def _run(
    command: Sequence[str | Path],
    *,
    env: Mapping[str, str],
    cwd: Path = _REPO_ROOT,
    timeout: float = 45.0,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    rendered = [str(part) for part in command]
    completed = subprocess.run(  # noqa: S603 - command is constructed from trusted test inputs
        rendered,
        cwd=cwd,
        env=dict(env),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        input=input_text,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(rendered)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def _wait_for(
    probe: Callable[[], _T | None],
    *,
    timeout: float,
    description: str,
    interval: float = 0.2,
) -> _T:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = probe()
        except (AssertionError, OSError, subprocess.SubprocessError) as exc:
            last_error = exc
        else:
            if value is not None:
                return value
        time.sleep(interval)
    detail = f"; last error: {last_error}" if last_error is not None else ""
    raise AssertionError(f"timed out waiting for {description}{detail}")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@contextlib.contextmanager
def _logged_process(
    command: Sequence[str | Path], *, env: Mapping[str, str], log_path: Path
) -> Iterator[subprocess.Popen[str]]:
    rendered = [str(part) for part in command]
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603 - trusted acceptance commands only
            rendered,
            cwd=_REPO_ROOT,
            env=dict(env),
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            yield process
        finally:
            _stop_process(process)


def _hermes_command(
    hermes: Path,
    *,
    provider: str,
    model: str,
    prompt: str,
    resume: str | None = None,
) -> list[str]:
    command = [
        str(hermes),
        "chat",
        "--quiet",
        "--provider",
        provider,
        "--model",
        model,
        "--toolsets",
        "device",
        "--ignore-rules",
        "--query",
        prompt,
    ]
    if resume is not None:
        command.extend(["--resume", resume, "--no-restore-cwd"])
    return command


def _chat(
    hermes: Path,
    *,
    env: Mapping[str, str],
    provider: str,
    model: str,
    prompt: str,
    resume: str | None = None,
    timeout: float = 180.0,
) -> subprocess.CompletedProcess[str]:
    return _run(
        _hermes_command(hermes, provider=provider, model=model, prompt=prompt, resume=resume),
        env=env,
        cwd=Path(env["HERMES_HOME"]),
        timeout=timeout,
    )


def _write_policy(path: Path, notification_mode: str) -> None:
    path.write_text(
        "version: 1\n"
        "defaults:\n"
        f"  notifications.send: {notification_mode}\n"
        "  diagnostics.echo: always\n"
        "  device.status: always\n"
        "devices: {}\n"
        "default_device: {}\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _hermes_git_status(agent_dir: Path, env: Mapping[str, str]) -> str:
    return _run(
        ["git", "-C", agent_dir, "status", "--porcelain", "--untracked-files=all"],
        env=env,
    ).stdout


def _provision_plugin(home: Path, hermes: Path, env: Mapping[str, str]) -> None:
    plugin_parent = home / "plugins"
    plugin_parent.mkdir(parents=True)
    (plugin_parent / "hermes-device").symlink_to(
        _REPO_ROOT / "hermes-device-plugin" / "hermes_device_plugin",
        target_is_directory=True,
    )
    _run(
        [hermes, "plugins", "enable", "hermes-device"],
        env=env,
        cwd=home,
        input_text="n\n",
    )


def _assert_plugin_and_tools(hermes: Path, env: Mapping[str, str], home: Path) -> None:
    listed = _run([hermes, "plugins", "list", "--json", "--user"], env=env, cwd=home)
    plugins = json.loads(listed.stdout)
    matches = [plugin for plugin in plugins if plugin.get("name") == "hermes-device"]
    assert matches == [
        {
            "name": "hermes-device",
            "status": "enabled",
            "version": "0.0.0",
            "description": "Hermes Device Protocol capability bridge",
            "source": "user",
        }
    ], listed.stdout

    prompt_size = _run([hermes, "prompt-size", "--json"], env=env, cwd=home, timeout=90)
    assert _device_tool_count(prompt_size.stdout) == 3


def _wait_for_online_device(hermes: Path, env: Mapping[str, str], home: Path) -> str:
    def probe() -> str | None:
        result = _run([hermes, "hdp", "devices"], env=env, cwd=home)
        for line in result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) >= 4 and fields[3] == "online":
                return fields[0]
        return None

    return _wait_for(probe, timeout=20, description="the paired node to become online")


def _wait_for_approval(env: Mapping[str, str]) -> str:
    def probe() -> str | None:
        result = _run(["uv", "run", "hdp", "approvals", "list"], env=env)
        return _parse_pending_invocation_id(result.stdout)

    return _wait_for(probe, timeout=90, description="the ASK invocation to become pending")


def _wait_for_log_marker(path: Path, marker: str) -> None:
    _wait_for(
        lambda: True if marker in path.read_text(encoding="utf-8") else None,
        timeout=5,
        description=f"node log marker {marker!r}",
    )


def _node_invoke_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("received invoke invocation_id=")


def _acceptance_environment() -> tuple[Path, Path, str, str]:
    if os.environ.get("HDP_RUN_ACCEPTANCE") != "1":
        pytest.skip("real-Hermes acceptance requires HDP_RUN_ACCEPTANCE=1")
    hermes_value = os.environ.get("HDP_HERMES_BIN") or shutil.which("hermes")
    if not hermes_value:
        pytest.fail("HDP_RUN_ACCEPTANCE=1 requires hermes on PATH or HDP_HERMES_BIN")
    agent_dir = Path(
        os.environ.get("HDP_HERMES_AGENT_DIR", Path.home() / ".hermes" / "hermes-agent")
    ).expanduser()
    provider = os.environ.get("HDP_ACCEPTANCE_PROVIDER", "").strip()
    model = os.environ.get("HDP_ACCEPTANCE_MODEL", "").strip()
    if not provider or not model:
        pytest.fail(
            "HDP_RUN_ACCEPTANCE=1 requires HDP_ACCEPTANCE_PROVIDER and HDP_ACCEPTANCE_MODEL"
        )
    return Path(hermes_value), agent_dir, provider, model


@pytest.mark.acceptance
@pytest.mark.timeout(1140)
def test_seed_success_criterion_clause_by_clause(tmp_path: Path) -> None:
    """Prove seed section 20 through unmodified Hermes and real subprocess boundaries."""
    hermes, agent_dir, provider, model = _acceptance_environment()
    home = tmp_path / "hermes-home"
    home.mkdir()
    env = {
        **os.environ,
        "HERMES_HOME": str(home),
        "HDP_BIND_PORT": "0",
        "NO_COLOR": "1",
        "PYTHONUNBUFFERED": "1",
        "TERM": "dumb",
    }

    # Clause 1: an exact, unmodified upstream Hermes checkout and interpreter.
    assert agent_dir.is_dir(), f"Hermes checkout does not exist: {agent_dir}"
    assert _run(["git", "-C", agent_dir, "rev-parse", "HEAD"], env=env).stdout.strip() == (
        _HERMES_COMMIT
    )
    before_status = _hermes_git_status(agent_dir, env)
    assert before_status == "", (
        f"upstream Hermes checkout is dirty before acceptance:\n{before_status}"
    )
    version = _run([hermes, "--version"], env=env, cwd=home).stdout
    assert _HERMES_VERSION in version
    assert f"Python: {_HERMES_PYTHON}" in version
    assert _parse_install_directory(version) == agent_dir.resolve(), (
        "hermes on PATH is not the executable from the verified checkout"
    )
    hermes_python = agent_dir / "venv" / "bin" / "python"
    assert _run([hermes_python, "--version"], env=env).stdout.strip() == (
        f"Python {_HERMES_PYTHON}"
    )
    _run([hermes_python, "-c", "import hdp_proto"], env=env)

    try:
        # Clause 2: Hermes loads the plugin and exposes exactly its three stable tools.
        _provision_plugin(home, hermes, env)
        _assert_plugin_and_tools(hermes, env, home)

        policy_path = home / "hdp" / "policy.yaml"
        policy_path.parent.mkdir(parents=True)
        _write_policy(policy_path, "deny")
        bridge_log = tmp_path / "bridge.log"
        node_log = tmp_path / "node.log"
        credential_file = tmp_path / "node.credential"

        with _logged_process(
            ["uv", "run", "hdp", "serve"], env=env, log_path=bridge_log
        ) as bridge:
            _wait_for(
                lambda: True if (home / "hdp" / "bridge.addr").exists() else None,
                timeout=10,
                description="hdp-bridge to publish bridge.addr",
            )
            assert bridge.poll() is None, bridge_log.read_text(encoding="utf-8")
            pair_code = _run(["uv", "run", "hdp", "pair", "new"], env=env).stdout.strip()

            with _logged_process(
                [
                    sys.executable,
                    "-m",
                    "hdp_reference_node",
                    "connect",
                    "--name",
                    "acceptance-node",
                    "--pair-code",
                    pair_code,
                    "--credential-file",
                    credential_file,
                ],
                env=env,
                log_path=node_log,
            ) as node:
                device_id = _wait_for_online_device(hermes, env, home)
                assert node.poll() is None, node_log.read_text(encoding="utf-8")

                # Clause 3: the always-visible status tool discovers the paired remote node.
                status = _chat(
                    hermes,
                    env=env,
                    provider=provider,
                    model=model,
                    prompt=(
                        "Call device_status_get exactly once. Then output its exact JSON result "
                        "with no commentary."
                    ),
                )
                assert device_id in status.stdout
                assert "notifications.send" in status.stdout
                assert "diagnostics.echo" in status.stdout
                assert "device.status" in status.stdout

                # Clause 4 and DENY half of clause 5: ordinary tool call, no node transmission.
                deny_marker = f"HDP-DENY-{uuid.uuid4().hex}"
                invokes_before_deny = _node_invoke_count(node_log)
                denied = _chat(
                    hermes,
                    env=env,
                    provider=provider,
                    model=model,
                    prompt=(
                        "Call device_notifications_send exactly once with title "
                        f"'Denied acceptance check' and body '{deny_marker}'. Do not call any "
                        "other tool. Output the exact tool result JSON with no commentary."
                    ),
                )
                assert "policy_denied" in denied.stdout
                time.sleep(0.5)
                assert _node_invoke_count(node_log) == invokes_before_deny

                # ASK half of clause 5 and clause 6: a second process approves the blocked chat.
                _write_policy(policy_path, "ask")
                notification_marker = f"HDP-NOTIFY-{uuid.uuid4().hex}"
                echo_marker = f"HDP-ECHO-{uuid.uuid4().hex}"
                ask_prompt = (
                    "Perform these actions in order. (1) Call device_notifications_send once "
                    "with title 'Approved acceptance check' and body "
                    f"'{notification_marker}'. (2) After it succeeds, call hdp_echo exactly "
                    f'once with payload {{"acceptance_echo":"{echo_marker}"}}. (3) Call '
                    "device_status_get exactly once. Then output a JSON object containing the "
                    "exact hdp_echo and device_status_get tool results with no commentary."
                )
                ask_process = subprocess.Popen(  # noqa: S603 - trusted Hermes executable
                    _hermes_command(hermes, provider=provider, model=model, prompt=ask_prompt),
                    cwd=home,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                try:
                    invocation_id = _wait_for_approval(env)
                    approved = _run(
                        [
                            "uv",
                            "run",
                            "hdp",
                            "approvals",
                            "approve",
                            invocation_id,
                            "--scope",
                            "one_time",
                        ],
                        env=env,
                    )
                    approval_reply = json.loads(approved.stdout)
                    assert approval_reply["ok"] is True
                    assert approval_reply["state"] == "approved"
                    ask_stdout, ask_stderr = ask_process.communicate(timeout=180)
                except BaseException:
                    _stop_process(ask_process)
                    raise
                assert ask_process.returncode == 0, (
                    f"ASK chat failed ({ask_process.returncode})\n"
                    f"stdout:\n{ask_stdout}\nstderr:\n{ask_stderr}"
                )
                _wait_for_log_marker(node_log, notification_marker)
                _wait_for(
                    lambda: (
                        True if _node_invoke_count(node_log) >= invokes_before_deny + 2 else None
                    ),
                    timeout=5,
                    description="notification and echo invoke frames at the node",
                )
                assert re.search(r'"ok"\s*:\s*true', ask_stdout)
                assert echo_marker in ask_stdout
                assert device_id in ask_stdout
                session_id = _parse_session_id(ask_stderr)

                # Clause 7: resume the same session and recall a value produced only by the
                # prior device_status_get result. The device id never appears in ask_prompt.
                assert device_id not in ask_prompt
                resumed = _chat(
                    hermes,
                    env=env,
                    provider=provider,
                    model=model,
                    resume=session_id,
                    prompt=(
                        "Reply with only the exact device_id from the previous "
                        "device_status_get tool result. Do not call a tool."
                    ),
                )
                assert resumed.stdout.strip() == device_id
    finally:
        after_status = _hermes_git_status(agent_dir, env)
        assert after_status == before_status == "", (
            "acceptance changed the upstream Hermes checkout:\n"
            f"before:\n{before_status}\nafter:\n{after_status}"
        )


def test_session_id_parser_accepts_quiet_mode_stderr() -> None:
    assert _parse_session_id("warning\n\nsession_id: 20260819_101112_abcd\n") == (
        "20260819_101112_abcd"
    )


def test_install_directory_parser_binds_hermes_executable_to_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "hermes-agent"
    output = f"Hermes Agent v0.20.0 (2026.8.3)\nInstall directory: {checkout}\nPython: 3.11.15\n"

    assert _parse_install_directory(output) == checkout.resolve()


def test_install_directory_parser_rejects_missing_field() -> None:
    with pytest.raises(AssertionError, match="Install directory"):
        _parse_install_directory("Hermes Agent v0.20.0\nPython: 3.11.15\n")


def test_pending_approval_parser_ignores_empty_state() -> None:
    assert _parse_pending_invocation_id("[]\n") is None
    assert (
        _parse_pending_invocation_id(
            '[{"invocation_id":"01K123456789ABCDEFGHJKMNPQ","device_id":"dev_456"}]\n'
        )
        == "01K123456789ABCDEFGHJKMNPQ"
    )
    assert _parse_pending_invocation_id("no pending approvals\n") is None
    assert (
        _parse_pending_invocation_id(
            "inv_123\tdev_456\tnotifications.send@1\ttitle=Build\t2030-01-01T00:00:00Z\n"
        )
        == "inv_123"
    )
    assert (
        _parse_pending_invocation_id(
            "01K123456789ABCDEFGHJKMNPQ\tdev_456\tnotifications.send@1\t"
            "title=Build\t2030-01-01T00:00:00Z\n"
        )
        == "01K123456789ABCDEFGHJKMNPQ"
    )


def test_device_tool_count_reads_public_prompt_size_shape() -> None:
    output = json.dumps(
        {
            "toolsets_breakdown": [
                {"toolset": "terminal", "tool_count": 4},
                {"toolset": "device", "tool_count": 3},
            ]
        }
    )
    assert _device_tool_count(output) == 3


def test_node_invoke_count_uses_protocol_receive_log(tmp_path: Path) -> None:
    node_log = tmp_path / "node.log"
    node_log.write_text(
        "connected as device_id=dev_1\n"
        "received invoke invocation_id=one capability=diagnostics.echo version=1\n"
        "application output\n"
        "received invoke invocation_id=two capability=notifications.send version=1\n",
        encoding="utf-8",
    )

    assert _node_invoke_count(node_log) == 2
