# Hermes Device Protocol

Hermes Device Protocol (HDP) lets Hermes discover and invoke capabilities provided by connected
devices. This repository contains the HDP/0 wire protocol, a profile-scoped bridge daemon, the
Hermes plugin, and a Python reference node.

## Current state

The current implementation provides:

- HDP/0 over WebSocket at `/hdp/v0/socket`, with capability advertisement, invocation,
  acknowledgements, results, cancellation, heartbeats, reconnect backoff, and protocol errors.
- A long-running `hdp-bridge` daemon with SQLite-backed device identity and capability persistence,
  one-time pairing codes, hashed credentials, revocation, policy enforcement, approvals, presence
  tracking, and an append-only audit log.
- A Hermes plugin exposing `device_status_get`, `device_notifications_send`, and `hdp_echo`, plus
  `hermes hdp` operator commands and the `/hdp` diagnostic command.
- `hdp-node`, a working Python reference node and protocol/conformance test fixture.
- A platform-neutral contract suitable for Linux, Android, or another platform. This repository
  does not contain a packaged Android application.

The bridge binds to `127.0.0.1:8765` by default. State is isolated per Hermes profile under
`$HERMES_HOME/hdp/`. Remote binding is disabled unless explicitly enabled with `HDP_ALLOW_REMOTE=1`;
use TLS or a trusted tunnel before exposing a bridge beyond localhost.

## Install from source

Requirements: Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync
uv run hdp-bridge --help
uv run hdp-node --help
```

This installs all workspace packages into the project environment. The protocol codec (`hdp-proto`)
is stdlib-only; the bridge, plugin, and reference node use their declared runtime dependencies.

## Run the bridge as a service (Linux, recommended)

`uv run hdp-bridge serve` is fine for a quick check but ties the daemon to a terminal — close the
window and it's gone. For anything long-lived, install it as a `systemd --user` unit instead:

```bash
uv sync                # populate .venv/ first
make service-install   # installs, enables at boot (linger), and starts it now
```

This renders `deploy/systemd/hdp-bridge.service.in` into
`~/.config/systemd/user/hdp-bridge.service` for the current user and `$HOME/.hermes` profile
(override with `HERMES_HOME_DIR=...`), then starts it. Manage it with:

```bash
make service-status    # systemctl --user status
make service-logs      # journalctl --user -u hdp-bridge.service -f
make service-uninstall # stop, disable, remove the unit
```

Crashes restart automatically (`Restart=on-failure`); `loginctl enable-linger` means it also starts
at boot and survives logout, without needing root.

## Run the bridge and connect a node

Use the same `HERMES_HOME` for the bridge and node, or pass the bridge URL explicitly.

Terminal 1 — start the bridge (skip this if it's already running as a service above):

```bash
export HERMES_HOME="$HOME/.hermes"
uv run hdp-bridge serve
```

Terminal 2 — mint a one-time pairing code:

```bash
export HERMES_HOME="$HOME/.hermes"
uv run hdp-bridge pair new
```

Terminal 3 — pair and run the reference node. Replace the placeholder with the code printed by
the previous command:

```bash
export HERMES_HOME="$HOME/.hermes"
uv run hdp-node connect \
  --name workshop-node \
  --pair-code XXXX-XXXX-XXXX \
  --credential-file "$HOME/.config/hdp/workshop-node.credential"
```

The credential file is created with mode `0600`. After the first successful pairing, restart the
node without the pairing code; it reuses the stored credential and reconnects with exponential
backoff and jitter:

```bash
uv run hdp-node connect \
  --name workshop-node \
  --credential-file "$HOME/.config/hdp/workshop-node.credential"
```

The reference node discovers the endpoint from `$HERMES_HOME/hdp/bridge.addr`. A client on another
machine or profile can provide the URL directly:

```bash
uv run hdp-node connect \
  --name workshop-node \
  --url ws://127.0.0.1:8765/hdp/v0/socket \
  --credential-file "$HOME/.config/hdp/workshop-node.credential"
```

For an Android emulator, the host is normally reachable as `10.0.2.2`; configure the app with
`ws://10.0.2.2:8765/hdp/v0/socket` and pair using the same bridge. Keep credentials in protected
platform storage.

## Operate the bridge

The bridge must be running for live device status and invocations. Commands use the active
`HERMES_HOME` profile:

```bash
uv run hdp-bridge devices revoke DEVICE_ID
uv run hdp-bridge audit tail
uv run hdp-bridge approvals list
uv run hdp-bridge approvals approve INVOCATION_ID --scope one_time
uv run hdp-bridge approvals deny INVOCATION_ID
uv run hdp-bridge policy show
uv run hdp-bridge policy validate /path/to/policy.yaml
uv run hdp-bridge policy reload
```

The Hermes-facing read-only commands are:

```bash
hermes hdp status
hermes hdp devices
hermes hdp audit
```

Pairing and revocation are intentionally short-lived CLI operations:

```bash
hermes hdp pair --new
hermes hdp devices revoke DEVICE_ID
```

Use `hermes plugins list` to confirm that `hermes-device` is loaded. The plugin’s model-facing
tools return JSON and fail closed with a structured error when the bridge or device is unavailable.

## Install the plugin into Hermes

For a local Hermes installation, set `HERMES_VENV_PYTHON` if Hermes is not at the default path,
then run:

```bash
export HERMES_HOME="$HOME/.hermes"
export HERMES_VENV_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
make dev-install
hermes plugins enable hermes-device
hermes plugins list
```

For a named Hermes profile:

```bash
make dev-install-profile PROFILE=coder
HERMES_HOME="$HOME/.hermes/profiles/coder" hermes plugins enable hermes-device
```

Remove the default-profile development link with `make dev-uninstall`.

## Repository layout

```text
hdp-spec/                 HDP/0, errors, capability schemas, and hdp-proto
hdp-bridge/               standalone daemon, registry, policy, approvals, and control plane
hermes-device-plugin/     Hermes tools and Unix-socket bridge client
hdp-reference-node/       Python node implementation and CLI
tests/conformance/        cross-package wire and lifecycle tests
docs/developer-guide.md   application/node integration guide
docs/dev-setup.md         development and manual verification notes
```

Read [the developer guide](docs/developer-guide.md) to build an application that connects to HDP,
and [HDP/0](hdp-spec/HDP-0.md) for the normative wire behavior.

## Development checks

```bash
make check       # Ruff, formatting, mypy, and the full test suite
make test
make lint
make fmt-check
make typecheck
```

The credentialed Hermes acceptance test is separate because it requires a prepared Hermes
installation and a configured model provider:

```bash
export HDP_ACCEPTANCE_PROVIDER=<openrouter|openai|anthropic|nous>
export HDP_ACCEPTANCE_MODEL=<provider-model-id>
make acceptance
```
