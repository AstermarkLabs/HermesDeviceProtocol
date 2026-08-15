# Oracle

Hermes Device Expansion MVP scaffold.

This repository follows the M0-M4 plan in:

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

