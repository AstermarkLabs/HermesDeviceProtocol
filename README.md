# Oracle

Hermes Device Expansion MVP scaffold.

This repository follows the M0-M4 plan in:

- `/home/brian/Documents/c0de_box/docs/oracle-docs/docs/architecture.md`
- `/home/brian/Documents/c0de_box/docs/oracle-docs/docs/design.md`
- `/home/brian/Documents/c0de_box/docs/oracle-docs/docs/requirements.md`
- `/home/brian/Documents/c0de_box/docs/oracle-docs/docs/stack.md`
- `/home/brian/Documents/c0de_box/docs/oracle-docs/docs/m0-plan.md` through `m4-plan.md`

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

