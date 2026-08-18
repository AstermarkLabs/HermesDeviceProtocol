# HermesDeviceProtocol

Hermes Device Expansion MVP scaffold.

This repository follows the M0-M4 plan in [oracle-docs](https://github.com/AstermarkLabs/oracle-docs):

- `docs/architecture.md`
- `docs/design.md`
- `docs/requirements.md`
- `docs/stack.md`
- `docs/m0-plan.md` through `m4-plan.md`

Top-level shape:

- `hdp-spec/`: normative HDP/0 spec and stdlib-only `hdp_proto` codec package.
- `hermes-device-plugin/`: Hermes-facing plugin package.
- `hdp-bridge/`: M2+ daemon package.
- `hdp-reference-node/`: Python reference node and fault-injection package.
- `tests/`: cross-package unit, conformance, and M4 acceptance suites.
- `android/`: reserved for M5+.

## M0 status

M0 (plugin spike) is implemented and passed its exit gate (m0-plan.md §8) against a real Hermes
install — `make dev-install`, plugin discovery, all three tools returning correct JSON via
`hermes chat -q`, zero `event loop is closed` in the log, and an exact one-line (`hdp-proto`)
venv diff.

**Gateway-mode deviation from the literal gate procedure.** m0-plan.md §8 step 4 calls for
exercising the tool calls in gateway mode (a different `_run_async` branch than CLI — the
already-running-loop branch a disposable thread serves). The `default` Hermes profile's gateway
was live (an active Discord session, PID-bound) at verification time, so `hermes gateway run`
was not used — starting a second instance against the same platform credentials would have
risked disrupting that session. Instead, the already-running-loop branch was exercised directly:
a one-shot script called Hermes's real `hermes_cli.plugins.discover_plugins()` (the same loader
`chat -q` uses) and `tools.registry.registry.dispatch(...)` for all three tools from inside a
coroutine already running under `asyncio.run(...)` — the same precondition
`model_tools._run_async` branches on — then discarded. All three tools returned well-formed
results; three *sequential* dispatches inside one running loop means calls 2 and 3 ran after
call 1's disposable loop was destroyed, which is the exact failure ADR-0002 exists to prevent.

This is real evidence for the branch-1 loop-ownership property, but it did not go through
`hermes gateway run` and did not write to `~/.hermes/logs/agent.log` (so the `grep -ci "event
loop is closed"` check above covers the CLI runs only, not this probe — its own clean output was
the check). M1's exit gate re-asserts this same gateway-mode item (m1-plan.md §8); either run the
literal `hermes gateway run` procedure then (e.g. against a platform-free profile, or once the
`default` profile's gateway isn't live), or consciously carry this substitution forward.

## M1 status

M1 (real socket to a separate OS process) is implemented: the wire spec (`hdp-spec/HDP-0.md`,
`errors.md`, capability docs), a real `aiohttp`-backed embedded bridge server
(`hermes_device_plugin/transport/_server.py`, `_connection.py`, `embedded.py`), a real reference
node as a genuinely separate subprocess (`hdp-reference-node/`), invocation-lifecycle hardening
(ack timeout vs. execution deadline as two distinct futures, cancel, late-result handling,
malformed-frame and duplicate-envelope defenses), and a conformance suite
(`tests/conformance/test_faults.py`) driving the real node subprocess over a real socket through
the in-scope fault matrix. `make check` is green: ruff, format-check, mypy, and 127 pytest tests
(unit + wire-level `EmbeddedTransport` tests + the conformance suite).

**Exit gate results, against a real Hermes install (`make dev-install`):**

- Confirmed: `hermes-agent`'s venv already has `aiohttp` (3.14.1) — no M1-driven venv change, NFR-2
  amendment not needed.
- Confirmed: `hermes plugins list` shows `hermes-device` enabled with its 3 tools.
- Confirmed: `device_status_get` via `hermes chat -q` returns exactly
  `{"ok": true, "data": {"devices": []}}` (37 bytes), matching M0's shape with the M1 transport
  underneath — repeated across multiple separate `-q` invocations.
- **Not testable at M1, and why:** a real `hdp-node` subprocess connecting to a live Hermes-hosted
  bridge and completing an invocation end to end, driven through `hermes chat -q`. Each `-q`
  invocation is a short-lived process (D5: no persistent daemon), so the embedded bridge's bound
  port dies the instant that process exits — the reference node's reconnect-with-backoff essentially
  never lands a connection within one `-q` call's window before the process is already gone; see
  `/tmp/hdp_node_manual.log` from the verification attempt, which shows the node still retrying
  `Cannot connect to host 127.0.0.1:8765` for the entire ~5-minute window a `chat -q` session was
  kept open. This is a structural consequence of M1's own scope decision (the bridge lives inside
  the plugin process; extraction to a long-lived daemon is explicitly M2), not a gap in the
  implementation. The equivalent coverage that *is* exercised today is the conformance suite: 11
  tests drive a real `hdp-node` subprocess over a real socket against a real `EmbeddedTransport`
  instance, covering the full fault matrix (never-ack, slow-result, mid-call disconnect, malformed/
  duplicate/stale results, malformed envelopes, version mismatch, no-matching-device), plus 12
  wire-level tests against `_server.build_app(...)` directly. Revisit this gate item once M2 gives
  the bridge a lifetime independent of any single `chat -q` invocation.
- **Gateway mode: substitution carried forward from M0, not resolved.** At verification time, the
  `default` profile's gateway was live (PID 2082) *and* a second profile, `n8nian`, was also
  running its own live gateway (PID 1255258) with its own n8n MCP subprocess — no platform-free
  profile was available to run the literal `hermes gateway run` procedure against without risking
  disruption to a real session. Deferred to M2, where a long-lived bridge process makes standing up
  a dedicated test profile worth the cost.
- `grep -ci "event loop is closed" ~/.hermes/logs/agent.log` → `0` across all CLI-mode runs
  performed during this gate.

**Two real bugs found via real-install testing (both fixed, both now covered by
`hermes-device-plugin/tests/test_server_bind_lifecycle.py`):**

1. `HDPRuntime.close()` had a shutdown race: an earlier implementation signalled shutdown via
   `loop.call_soon_threadsafe(loop.stop)`, which could abort `transport.start()` mid-flight if
   `close()` was called immediately after construction, sometimes leaving a bound socket whose
   `AppRunner` was never assigned anywhere reachable — a real fd/thread leak. Fixed by replacing it
   with a `threading.Event`-based poll (`_serve_until_close_requested`) that always lets `start()`
   run to completion before checking for a close request. Verified via
   `tests/conformance/test_runtime_composition.py` (10 repeated start/stop cycles, no fd/thread
   growth) and repeated full-suite stress runs.
2. An intermittent `KeyError: 'HERMES_HOME'` was observed from the daemon thread's `os.environ`
   reads during `EmbeddedServer.start()`/`close()`, while running inside a real `hermes chat -q`
   session. The exact mechanism wasn't fully root-caused (it did not reproduce against this
   codebase in isolation, and did not appear in `~/.hermes/logs/agent.log`) — the working
   hypothesis is a race with Hermes's own `os.environ` mutation elsewhere in that process, which is
   outside this repo. Mitigated rather than "fixed" at the root: `_write_bridge_addr()` retries up
   to 3 times with a short delay on `KeyError` during `start()` (the socket is already bound by
   then, worth retrying rather than tearing down), and `EmbeddedServer.close()`'s best-effort
   `bridge.addr` cleanup swallows `KeyError`/`OSError` outright (D5: a stale `bridge.addr` is
   harmless, the next process's `start()` overwrites it).

## M2 status

M2 (registry, pairing, and bridge extraction) is implemented: the bridge now lives in its own
long-lived process (`hdp-bridge serve`) instead of inside the plugin, with a SQLite device
registry (`hdp_bridge/registry.py`, `store/db.py`, WAL, profile-scoped under `$HERMES_HOME/hdp/`),
one-time pairing codes and hashed device credentials (`pairing.py`, `credentials.py`), immediate
revocation with in-flight invocation failure (`revocation.py`, `connection.py`), presence /
dead-peer detection, an fsync'd append-only audit log (`audit.py`), a Unix-socket control plane
between plugin and daemon (`control.py`, `transport/socket.py`, mode 0600), daemon lifecycle with
a PID-as-claim single-instance guard (`daemon.py`), and a two-surface operator UI —
`hdp-bridge {serve,pair,devices,audit}`, `hermes hdp {status,devices,pair,audit}`, and `/hdp` —
rendered from one set of logic (FR-18). `make check` is green: ruff, `ruff format --check`, mypy,
and 265 pytest tests.

**Task 19 (daemon autostart) was cut.** It was the plan's own pre-declared optional cut line
("may be skipped entirely and M2 still passes its exit gate... implement only if time remains
after Task 18"). The recorded ruling: given repeated external session-limit interruptions across
this run (the Task 3, 7, 10, 12, and 15 implementers all hit mid-task usage limits and had to be
resumed by fresh agents), the task was cut and the run proceeded directly to the final
whole-branch review, per the plan's own guidance. Cost if wrong: a future session implements
Task 19 from the same plan file — cheap, additive, no rework of anything already built. The
shipped MVP answer for starting the bridge is therefore `hdp-bridge serve` run manually in a
foreground terminal (see `docs/dev-setup.md`).

**Four deviations from the plan/spec as written, all deliberate and documented in code:**

1. **Two SQLite connections in `daemon.py`, not one.** m2-plan.md describes a single
   `sqlite3.Connection` shared by `Registry`/pairing/credentials; `Registry.__init__` (Task 10)
   takes a `Path` and opens its own connection internally, so there is no single connection object
   to share. `_serve_claimed` therefore opens a second, independent connection onto the same file
   for `NodeConnection` to hand to `credentials.py`/`pairing.py`. Safe for three concrete reasons,
   spelled out in `daemon.py`'s own comment: (1) WAL mode makes one connection's committed writes
   immediately visible to the other on the same file; (2) the daemon is single-threaded and
   single-writer (§3.2), so no concurrent write ever races across the two connections; (3) the one
   place cross-connection ordering matters — `_handle_hello`'s pairing path, which writes the
   `devices` row via `registry` before `credentials.issue_credential` writes the FK-referencing
   `credentials` row via this connection — is deliberately written in that order precisely because
   the two connections are not one transaction. If `Registry` ever gains an injectable connection,
   this collapses back to the plan's original single-connection design.
2. **`POST /hdp/v0/pair` remains absent from the HTTP surface.** m2-plan.md mentions such a route;
   M2 implements pairing entirely through the WebSocket handshake's `pair:`-prefixed credential.
   A second HTTP round trip before the upgrade would need its own auth story for no benefit, since
   the pairing code is already the one-time secret. Recorded as the resolution of that ambiguity
   (not a silent drop) in `hdp-spec/HDP-0.md` §8 and its Amendments (v0.2) section, which also
   records `hello.credential` verification, the new optional `welcome.credential`, and `revoke`
   now being sent — all landed without a wire break (the envelope's `hdp` value is still `"0"`).
3. **`/hdp pair` and `/hdp devices revoke` are CLI-only** (final-review finding I1). Both open
   `registry.db` and the audit log directly, which is the plan's sanctioned exception to Global
   Constraint #1 for *short-lived operator CLI subcommands* — but in gateway mode `/hdp` runs
   inside the always-running plugin process, which quietly turned a separate-process exception
   into an in-process one. `/hdp` keeps the read-only verbs (`status`, `devices`, `audit`) and
   answers the two mutating ones with a pointer to `hermes hdp ...`. This also keeps a plaintext
   pairing code out of a gateway chat transcript.
4. **Gateway-mode verification is still substituted, not resolved** — the open loop M1's section
   deferred to M2. No gateway-mode run was performed in this milestone either (see the gate
   results below); the substitution is carried forward again rather than closed. It is now the
   oldest outstanding verification debt in this repo and should be paid at M3.

**Exit gate results (m2-plan.md §8 / the plan's Exit Gate section).** The steps that this repo's
own entry points can drive were run end to end against a throwaway `HERMES_HOME`; the steps that
require a real Hermes install or a live gateway were not run, and are marked as such rather than
assumed.

- **Step 1 — `hdp-bridge serve` (run):** foreground start writes `bridge.addr`, `bridge.pid`, and
  `bridge.sock`; `bridge.sock` is `srw-------` (0600) as required; all three are removed on clean
  shutdown, leaving only `registry.db` and `audit/`.
- **Step 2 — pair (run):** `hdp-bridge pair new` mints a code; `hdp-node connect --pair-code ...
  --name workshop-node` pairs, and the device appears via the `hermes hdp devices` handler as
  `state=active online=online` with a fresh `last_seen_at`. Three capabilities
  (`notifications.send`, `diagnostics.echo`, `device.status`) are advertised and persisted to the
  `capabilities` table. The node's credential file is written `-rw-------` (0600).
- **Step 3 — restart both sides (run):** with both daemon and node restarted and no pair code, the
  node reconnects on its stored credential; `hermes hdp devices` shows the *same* `device_id` with
  a fresh `last_seen_at`.
- **Step 4 — revoke (run):** `hdp-bridge devices revoke <id>` prints `revoked <id>`; the connected
  node logs `revoked by the bridge (revoked by operator); disconnecting and not reconnecting` and
  exits without retrying; the device shows `state=revoked online=offline`.
- **Step 5 — reconnect on a revoked credential (run):** `hdp-node connect` on the revoked
  credential exits non-zero with `authentication rejected by the bridge ... not reconnecting` and
  a one-line operator message — no traceback, no retry loop.
- **Step 6 — profile isolation (run, at CLI level, with a substitution):** the literal gate line is
  `HERMES_HOME=~/.hermes/profiles/coder hermes hdp devices`, which needs a real Hermes install.
  The equivalent was run directly against the plugin's own `hermes hdp devices` handler with two
  separate `HERMES_HOME` roots and two daemons: the profile with the paired device lists it, the
  second profile reports `no paired devices`. `hdp-bridge/tests/test_profile_isolation.py` is the
  unit-level counterpart (FR-17); the CLI-level check above is the stronger of the two, but it was
  run against a temporary profile root, not against a real `~/.hermes/profiles/*` profile.
- **Step 7 — audit (run):** `hdp-bridge audit tail` shows, in order,
  `daemon_start`, `pairing_code_minted`, `paired`, `daemon_stop`, `daemon_start`, `revoked`,
  `auth_failed (unknown_credential)` — every security-relevant event of the run above, fsync'd on
  write (`audit.py`).
- **Step 8 — manual ritual: NOT RUN.** Bridge-death survivability, the one-hour soak, gateway mode
  vs CLI mode, and `grep -ci "event loop is closed" ~/.hermes/logs/agent.log` all require the
  plugin installed into a real Hermes venv (`make dev-install`) and a live gateway session. Not
  performed in this environment: `make dev-install` mutates the real `hermes-agent` venv, and this
  machine's `default` and `n8nian` profiles have historically had live, PID-bound gateway sessions
  (see M0/M1 above) that a second instance could disrupt. The manual ritual is written up in
  `docs/dev-setup.md` for an operator to execute against a real install.
- **Also not run:** every step's *literal* `hermes hdp ...` invocation. The verification above
  calls `hermes_device_plugin.cli.main([...])` — the exact function `register_cli_command` hands
  Hermes as the `hdp` handler — so the renderers, the control-socket round trip, and the daemon
  are all genuinely exercised; what is not exercised is Hermes's own command registration and
  dispatch, which is what an install-backed gate would add.
- **Environment note found during the gate:** `$HERMES_HOME` deeper than roughly 90 characters
  makes `control.py`'s `bind()` fail with `OSError: AF_UNIX path too long` and an unhandled
  traceback (the sockaddr_un limit, 108 bytes). Real but environmental; it is not on any
  realistic profile path, and no fix was made in this fix wave.

**Final whole-branch review and fix wave.** The final review returned "Ready to merge WITH FIXES"
with 9 findings: 2 critical (C1 `make check` red, C2 a flaky conformance test) and 7 important
(I1 gateway-mode constraint violation, I2 FR-11 unasserted, I3 invocation multiplexing regression,
I4 fail-open revoke CLIs, I5 duplicated CLI domain logic, I6 accept-loop OSError fragility,
I7 reference-node auth gaps, I8 missing FR-14 backoff jitter, I9 this README section). All 9 were
addressed in the fix wave (commits `324cabd`, `3fe91b7`, `472a3fd`, `db8eee7`), plus a follow-up
hardening the reference node's credential-file write with `O_NOFOLLOW` against symlink redirection
(`5a1e2c9`). Ten Minor findings (M1-M10) were triaged as deferred, not fixed; they are recorded in
the run's ledger. The full fix-wave write-up is in the run's `final-fix-report.md`.
