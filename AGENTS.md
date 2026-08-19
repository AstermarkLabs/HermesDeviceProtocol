# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.11–3.12 `uv` workspace for the Hermes Device Protocol (HDP).

- `hdp-spec/` contains the HDP/0 specification, capability documents, and the stdlib-only `hdp_proto` codec.
- `hermes-device-plugin/` provides the Hermes-facing plugin and its transport client.
- `hdp-bridge/` is the long-running daemon, SQLite registry, WebSocket server, and control plane.
- `hdp-reference-node/` is a test/reference device node with fault-injection support.
- Package tests live beside each package; `tests/conformance/` covers cross-package protocol behavior. `docs/` holds architecture, ADRs, setup guidance, and milestone plans.

Keep dependencies directional: protocol code stays independent; the plugin may depend on the bridge, but bridge code must not import the plugin.

## Build, Test, and Development Commands

Run commands from the repository root:

- `make test` — run the full pytest suite.
- `make lint` — run Ruff lint checks.
- `make fmt` / `make fmt-check` — apply or verify Ruff formatting.
- `make typecheck` — run the configured mypy checks.
- `make check` — run linting, format verification, type checks, and tests; use this before opening a PR.

For local Hermes integration, `make dev-install` links the plugin into the configured Hermes home and installs `hdp-proto` into its virtual environment. It changes local Hermes state; use `make dev-uninstall` to remove the link.

## Coding Style & Naming Conventions

Use four-space indentation, Python type annotations, and Ruff's 100-character line limit. Ruff enforces error, import, upgrade, bugbear, async, and security rules; format with Ruff rather than hand-formatting. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and `test_<behavior>.py` / `test_<behavior>` names for tests. Keep protocol and error changes synchronized with the relevant documents under `hdp-spec/`.

## Testing Guidelines

Add focused package tests with implementation changes and conformance tests for wire-visible behavior. Async tests use `pytest-asyncio` automatically; the suite has a 30-second timeout. Exercise failures deliberately: malformed envelopes, authentication failures, cancellation, and reconnect behavior are core protocol concerns.

## Commit & Pull Request Guidelines

Recent history uses concise, imperative, scope-led subjects such as `M2: SQLite-backed Registry — devices and capabilities survive daemon restarts` and `M2 final-review fixes: ...`. Follow that pattern: state the milestone/component, then the behavior changed. Keep commits narrowly scoped. PRs should explain the behavioral change, link the applicable requirement or ADR when relevant, list validation commands run, and call out any manual Hermes or gateway verification that remains unrun.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
