See @AGENTS.md for project structure, build/test commands, style, testing, and commit conventions.

## Working Style
- Milestones (M0-M4) are plan-driven; see `docs/m0-plan.md` through `m4-plan.md` and each plan's exit gate before marking milestone work done.
- Dependency direction is load-bearing: protocol code independent; plugin may depend on bridge; bridge must never import plugin. Don't introduce an import that violates this.
- `make dev-install` mutates local Hermes state (links plugin into Hermes home). Confirm before running; `make dev-uninstall` reverses it.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
