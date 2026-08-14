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

