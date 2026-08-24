# End-user release and update design

## Context

HDP currently has only a source-checkout workflow. Running or updating it requires a user to
activate or address the checkout environment, run `uv sync`, and separately refresh the bridge,
protocol package, Hermes plugin, and service. The existing systemd unit also runs the checkout's
`.venv`, which is unsuitable for a supported end-user installation.

This design introduces a release-backed, single-command lifecycle while retaining the current
editable developer workflow unchanged.

## Scope

This work provides:

- a versioned HDP release distribution that pins mutually compatible components;
- a one-time bootstrap script that creates a managed installation without a source checkout;
- `hdp update [VERSION]`, which upgrades the release as one coordinated operation;
- Hermes plugin integration and a systemd user service that use the managed installation; and
- automated coverage for the update orchestration and its failure boundaries.

It does not publish releases, change device protocol semantics, migrate user state, or replace
the existing developer commands.

## Distribution model

Publish a `hermes-device-protocol` meta-package for each supported HDP release. Its dependencies
pin exact compatible versions of `hdp-bridge`, `hdp-proto`, `hermes-device-plugin`, and
`hdp-reference-node`. The package exposes the existing `hdp` command and includes the plugin
asset needed by Hermes.

The release version is the compatibility boundary. End users request either the latest stable
release or an explicit version; they never resolve four independently selected packages.

## Installation layout

The release installer creates an HDP-owned environment in a user-local data directory, outside
the source checkout. It puts a small launcher on `PATH` that invokes that environment's `hdp`
command. The installer records the selected release version and installation root in an
HDP-owned manifest.

The systemd user unit executes the managed `hdp serve` path. It retains the existing
profile-scoped `HERMES_HOME` data directory, so bridge state stays separate from program files.

The contributor commands (`uv sync`, `make dev-install`, `make service-install`) retain their
checkout-based behavior and are documented as development-only.

## Bootstrap and update flow

`install-hdp` requires `uv` and a supported Python version. It installs the selected release into
the managed environment, configures the Hermes plugin, installs or replaces the managed service,
and starts it after successful setup.

`hdp update [VERSION]` follows this sequence:

1. Read the installation manifest and validate that the installation is managed.
2. Determine the requested release (`latest` when omitted).
3. Stop the managed user service only when it is active.
4. Resolve and install the full release into the managed environment.
5. Refresh the Hermes plugin files and install the release-matched, stdlib-only `hdp-proto` into
   the configured Hermes environment.
6. Validate that the new `hdp` executable is runnable and that the generated service references
   the managed executable.
7. Restart the service only after the preceding steps succeed, then report the installed version.

The command must accept an explicit release version, allowing an operator to pin or roll back to
a previously published compatible release.

## State, error handling, and recovery

HDP does not alter `$HERMES_HOME/hdp/` during installation or update. This preserves the bridge
database, schema migrations, pairings, credentials, policy, and audit history.

The updater reports failures by phase: service stop, package resolution/install, Hermes
integration, verification, or service restart. A failure never launches the service against a
known partial integration. If it stopped a previously active service, it makes a best-effort
attempt to restart the prior known-good managed release and reports whether recovery succeeded.

The installer and updater do not operate on a checkout-based developer installation. They explain
that the user should use the existing development commands instead.

## Testing

Unit tests cover manifest validation, latest and explicit-version resolution, command construction,
plugin refresh, and service-unit rendering. Orchestration tests use mocked package and systemd
operations to cover:

- successful update and restart of a running service;
- successful update when the service was stopped;
- failure before service shutdown;
- failure after shutdown with recovery of the previous release;
- no mutation of profile-scoped state; and
- refusal to run on an unmanaged/developer installation.

Manual Linux verification installs a released build into a fresh `HERMES_HOME`, pairs a reference
node, updates to a later released build, and confirms the service, plugin, and existing pairing
continue to work.

## Acceptance criteria

An end user can install and update HDP without activating a virtual environment, running `uv sync`,
or manually updating any HDP constituent. The command has one release version as its input and
either completes with the managed bridge running that version or reports a failed phase without
damaging profile-scoped state.
