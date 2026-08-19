# Graph Report - .  (2026-08-18)

## Corpus Check
- Corpus is ~48,091 words - fits in a single context window. You may not need a graph.

## Summary
- 1123 nodes · 2565 edges · 80 communities (65 shown, 15 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 181 edges (avg confidence: 0.53)
- Token cost: 0 input · 98,882 output

## Community Hubs (Navigation)
- Bridge Node Connection Handling
- Cross-Doc Governance & Capability Rationale
- M2 Conformance Test Harness
- Control Plane Frame Dispatch
- In-Memory Invocation Tracking
- ULID Minting & Parsing
- Bridge Transport Base & Status
- Socket Transport Client Tests
- Bridge Control Server
- Hermes /hdp Slash Command
- HDP Runtime Event Loop
- Bridge Socket Transport Client
- SQLite Store & Migrations
- Capability Descriptor Validation
- hdp-bridge CLI Revoke Rendering
- HDP Error Envelope Helpers
- Bridge Server Bind Lifecycle
- Plugin Profile Config Paths
- Bridge aiohttp App & Health
- Audit Log & Revocation
- HDPRuntime Singleton
- Bridge Hello Auth Branch Tests
- Reference Node Auth Tests
- Frame Handler Dispatch (Node/Bridge)
- Control Verb Handlers & Cancel
- Pairing Code Minting
- Wire Message Ack/Heartbeat/Progress
- Plugin Engine Invoke Tests
- Node Auth Failure & Fault Injection
- Bridge Daemon Profile Config
- Device Credential Issuance
- Invocation Revocation Failure
- Plugin Async Tool Handlers
- Reference Node Connect & Backoff
- Typed Wire Message Dataclasses
- BridgeTransport Protocol & Approvals
- Reference Node CLI & Fault Flags
- hermes hdp CLI Rendering Tests
- Plugin Tool Registration Tests
- device_status_get Handler Tests
- Devices Revoke CLI Fallback
- hermes hdp CLI Entry Point
- Plugin Engine & Tool Schemas
- Bridge Bind Host/Port Config
- Daemon PID Claim Guard
- Daemon Serve Bind Failure Tests
- Operator Revoke Orchestration
- Registry Schema Tables
- Bridge Server Wire-Level Tests
- HDP Envelope & Version Errors
- ResultMsg Wire Round-Trip
- InvokeMsg Wire Contract
- Capabilities Message Wire Format
- errors.md Conformance Tests
- hermes hdp Command Registration
- Welcome Message Credential Field
- CancelMsg Best-Effort Send
- uv Workspace Package Manifests
- device.status@1 Reference Handler
- diagnostics.echo@1 Reference Handler
- notifications.send@1 Reference Handler
- hermes hdp status Rendering
- Plugin Test Fixtures
- Repo Scaffold Sanity Test
- Control Socket Test Fixtures
- Pending Approval Scaffold
- Permission Policy Engine Scaffold
- Reference Node Capabilities Package
- HDP Frame Handling Rules
- Plugin Transport Package Init
- ambiguous_device Error Code
- approval_denied Error Code
- approval_timeout Error Code
- bridge_unavailable Error Code
- capability_unsupported Error Code
- no_matching_device Error Code
- not_implemented Error Code
- policy_denied Error Code
- version_incompatible Error Code
- HDP Binary Payload Rule

## God Nodes (most connected - your core abstractions)
1. `NodeConnection` - 73 edges
2. `InvocationsMem` - 64 edges
3. `Registry` - 64 edges
4. `Envelope` - 50 edges
5. `SocketTransport` - 46 edges
6. `AuditWriter` - 41 edges
7. `connect()` - 39 edges
8. `ControlServer` - 37 edges
9. `DeviceRecord` - 28 edges
10. `CapabilityDescriptor` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Dependency Direction Rule (protocol independent, plugin may depend on bridge, bridge must not import plugin)` --semantically_similar_to--> `Deviation: two SQLite connections in daemon.py, not one`  [INFERRED] [semantically similar]
  AGENTS.md → README.md
- `test_render_pair_new_mints_a_code_and_records_no_plaintext_audit_entry()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `_InvokeRequestLike` --uses--> `CapabilityDescriptor`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/capabilities.py
- `_InvokeRequestLike` --uses--> `Envelope`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/envelope.py
- `_InvokeRequestLike` --uses--> `EnvelopeError`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/envelope.py

## Import Cycles
- 3-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 4-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 5-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`

## Hyperedges (group relationships)
- **HDP Closed Error-Code Taxonomy Members** — hdp_spec_errors_taxonomy, hdp_spec_errors_bridge_unavailable, hdp_spec_errors_not_implemented, hdp_spec_errors_no_matching_device, hdp_spec_errors_capability_unsupported, hdp_spec_errors_ambiguous_device, hdp_spec_errors_device_offline, hdp_spec_errors_invocation_timeout, hdp_spec_errors_malformed_result, hdp_spec_errors_version_incompatible, hdp_spec_errors_auth_failed, hdp_spec_errors_policy_denied, hdp_spec_errors_approval_denied, hdp_spec_errors_approval_timeout, hdp_spec_errors_revoked, hdp_spec_errors_late_result, hdp_spec_errors_schema_drift [EXTRACTED 0.95]
- **Three MVP HDP Capabilities Advertised by Reference Node** — hdp_spec_capabilities_device_status_1, hdp_spec_capabilities_diagnostics_echo_1, hdp_spec_capabilities_notifications_send_1, hdp_spec_hdp_0_capability_descriptors [EXTRACTED 0.95]
- **hermes-device Plugin Tools Provided by plugin.yaml** — hermes_device_plugin_hermes_device_plugin_plugin_yaml_manifest, hermes_device_plugin_tool_device_notifications_send, hermes_device_plugin_tool_device_status_get, hermes_device_plugin_tool_hdp_echo [EXTRACTED 0.95]

## Communities (80 total, 15 thin omitted)

### Community 0 - "Bridge Node Connection Handling"
Cohesion: 0.05
Nodes (44): NodeConnection, Connection, WebSocketResponse, Per-connection lifecycle for one node's WebSocket. One `NodeConnection` per…, Started alongside `run()`'s own read loop and reaped in that same `finally`, on…, M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing…, Append now, drop anything outside the 60s window, and report whether the…, Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node… (+36 more)

### Community 1 - "Cross-Doc Governance & Capability Rationale"
Cohesion: 0.06
Nodes (42): Dependency Direction Rule (protocol independent, plugin may depend on bridge, bridge must not import plugin), make check (lint, format, typecheck, tests), Repository Guidelines (AGENTS.md), Working Style (CLAUDE.md), CI Workflow (make check), device.status@1 capability, device.status@1 is deliberately not what device_status_get calls, diagnostics.echo@1 capability (+34 more)

### Community 2 - "M2 Conformance Test Harness"
Cohesion: 0.10
Nodes (38): Process, bridge(), bridge_log(), _bridge_proc(), bridge_url(), _hermes_home(), fixture, Shared fixtures for the M2 conformance suite (m1-plan.md §7, m2-plan.md). HDP… (+30 more)

### Community 3 - "Control Plane Frame Dispatch"
Cohesion: 0.14
Nodes (39): read_frame(), write_frame(), _connect_and_hello(), _ctl_invoke(), _ctl_invoke_envelope(), `hdp_bridge.control` — the plugin↔bridge Unix-socket control plane.…, Finding I3, server half: `_handle` used to `await self._dispatch(...)` inline…, The corollary finding I3 names: the read loop must keep servicing other verbs —… (+31 more)

### Community 4 - "In-Memory Invocation Tracking"
Cohesion: 0.08
Nodes (28): InvocationsMem, PendingInvocation, Any, The bridge-side pending-invocation table — id → in-flight state. Backs real…, Fail every pending invocation regardless of device — used on transport shutdown…, A device's connection dropped (or was revoked): fail every invocation still…, Remove and fail every pending entry (all of them when `device_id` is `None`).…, Tracks in-flight invocations. Empty by construction; entries live only between… (+20 more)

### Community 5 - "ULID Minting & Parsing"
Cohesion: 0.10
Nodes (30): _decode_crockford(), _encode_crockford(), InvalidULIDError, is_valid(), new(), parse(), ValueError, Hand-rolled ULID mint/parse — stdlib only, no `ulid` dependency (SDR-3). A ULID… (+22 more)

### Community 6 - "Bridge Transport Base & Status"
Cohesion: 0.11
Nodes (19): BridgeStatus, DeviceInfo, InvokeRequest, `BridgeTransport` — the ADR-0004 extraction seam. `engine.py` depends on this…, One capability invocation, fully resolved by `engine.py` before it reaches the…, InprocTransport, _LoopbackInvocations, _LoopbackRegistry (+11 more)

### Community 7 - "Socket Transport Client Tests"
Cohesion: 0.15
Nodes (25): Implements `BridgeTransport` (verified structurally by the tests, not by…, SocketTransport, bridge_daemon(), fake_control_server(), _FakeControlServer, _invoke_request(), fixture, `SocketTransport` — the plugin-side client of `hdp_bridge/control.py`'s Unix-… (+17 more)

### Community 8 - "Bridge Control Server"
Cohesion: 0.11
Nodes (21): ControlServer, _correlate(), _invoke_failure(), _InvokeReq, _log_task_exception(), Any, StreamReader, StreamWriter (+13 more)

### Community 9 - "Hermes /hdp Slash Command"
Cohesion: 0.12
Nodes (23): _dispatch(), handle_hdp_command(), Any, Hermes `/hdp status|devices|audit` slash command — the **read-only** half of…, `args` is accepted as either a raw string (split on whitespace here) or an…, Registers `/hdp` (design §2's confinement rule — this module is one of the…, register_command(), _hermes_home() (+15 more)

### Community 10 - "HDP Runtime Event Loop"
Cohesion: 0.11
Nodes (17): AbstractEventLoop, HDPRuntime, Any, Future, T, Explicit teardown for tests (`lazy_singleton`'s `.reset()` only drops the…, Owns a daemon thread and the `asyncio` loop running on it. Constructed exactly…, `await self.transport.start()` runs to completion before anything checks… (+9 more)

### Community 11 - "Bridge Socket Transport Client"
Cohesion: 0.11
Nodes (13): CapabilityInfo, _bridge_unavailable(), Future, StreamReader, StreamWriter, M2 Unix-socket bridge transport — the client half of `hdp_bridge/control.py`'s…, Attempt to (re)connect. Must be called with `self._lock` held. Returns `True`…, Demultiplex every reply on one connection into the future that is waiting for… (+5 more)

### Community 12 - "SQLite Store & Migrations"
Cohesion: 0.14
Nodes (18): _apply_pragmas(), connect(), _migrate(), Connection, Path, RuntimeError, SQLite connection factory and forward-only migration runner (§3.1, §3.2)., The database's `schema_version` is higher than this build of `hdp_bridge` knows… (+10 more)

### Community 13 - "Capability Descriptor Validation"
Cohesion: 0.15
Nodes (19): Any, ValueError, Capability descriptors and output-schema validation. `CapabilityDescriptor` is…, Raised by `validate_output` when `data` does not match `output_schema`. The…, Never `cls(**d)` — read fields by name, tolerate unknown fields, matching the…, Validate `data` against `descriptor.output_schema`. Raises…, SchemaValidationError, _validate() (+11 more)

### Community 14 - "hdp-bridge CLI Revoke Rendering"
Cohesion: 0.15
Nodes (19): main(), Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback…, _run_audit_tail(), _run_devices_revoke(), _run_pair_new(), True when `revoke()`'s return value describes a failure rather than a completed…, revoke_failed(), _insert_device_with_credential() (+11 more)

### Community 15 - "HDP Error Envelope Helpers"
Cohesion: 0.15
Nodes (16): BaseException, err(), Error, ErrorCode, ok(), Any, The closed HDP error-code taxonomy and the model-facing result envelope.…, Build the failure half of the model-facing result envelope. `detail` becomes… (+8 more)

### Community 16 - "Bridge Server Bind Lifecycle"
Cohesion: 0.14
Nodes (17): ConnectionFactory, HdpServer, Path, Owns the `AppRunner`/`TCPSite` pair and the `bridge.addr` discovery file., _write_bridge_addr(), _noop_connection_factory(), `HdpServer.start()`/`close()` bind-lifecycle edge cases — specifically the two…, Global Constraint: `hdp_bridge` must never import from `hermes_device_plugin` —… (+9 more)

### Community 17 - "Plugin Profile Config Paths"
Cohesion: 0.14
Nodes (18): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), Path (+10 more)

### Community 18 - "Bridge aiohttp App & Health"
Cohesion: 0.15
Nodes (17): Application, _blobs_reserved(), _bound_port(), build_app(), _health(), _make_socket_handler(), Any, WebSocketResponse (+9 more)

### Community 19 - "Audit Log & Revocation"
Cohesion: 0.16
Nodes (12): AuditWriter, Path, Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON…, Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb —…, Operator-initiated revocation (FR-15, §4.4) — immediate and total, four steps…, Exercises O_APPEND directly: two separate `record()` calls (two separate…, `os.fsync` is actually invoked for events in the security-relevant subset, not…, test_no_plaintext_credential_ever_reaches_the_audit_file() (+4 more)

### Community 20 - "HDPRuntime Singleton"
Cohesion: 0.15
Nodes (16): get_runtime(), `HDPRuntime` — the pattern the whole architecture bets on (ADR-0002,…, The one `HDPRuntime` for this process, built at first use. Do not call this…, lazy_singleton(), T, Stdlib fallback for `plugins.plugin_utils.lazy_singleton`, used only when no…, _clean_runtime_singleton(), fixture (+8 more)

### Community 21 - "Bridge Hello Auth Branch Tests"
Cohesion: 0.23
Nodes (12): _FakeWS, `_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired…, _read_audit_records(), test_hello_with_a_previously_consumed_pairing_code_is_auth_failed(), test_hello_with_a_returning_credential_resolves_the_same_device_id(), test_hello_with_a_revoked_credential_is_auth_failed(), test_hello_with_a_valid_pairing_code_pairs_and_returns_a_credential(), test_hello_with_an_invalid_pairing_code_is_auth_failed() (+4 more)

### Community 22 - "Reference Node Auth Tests"
Cohesion: 0.12
Nodes (15): AppRunner, Python HDP reference node package., _abrupt_close_handler(), _auth_failed_handler(), bridge_stub(), _pairing_handler(), fixture, The reference node's M2 auth behaviour (final-review findings I7 and I8).… (+7 more)

### Community 23 - "Frame Handler Dispatch (Node/Bridge)"
Cohesion: 0.19
Nodes (7): Operator-only verb (FR-15, §4.4) — the CLI's `hdp-bridge devices revoke`…, _NodeSession, Any, Per-connection dispatch state: which invocation ids have been cancelled by the…, M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a…, Envelope, An HDP/0 frame. `payload` is opaque to this layer — Hermes…

### Community 24 - "Control Verb Handlers & Cancel"
Cohesion: 0.14
Nodes (8): Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call…, Operator-only verb (`hermes hdp devices` at Task 17 was ultimately built…, Operator-only verb backing `hermes hdp audit` / `/hdp audit` — read-only, but…, `Server.close()` alone leaves already-accepted connections open — without this,…, test_close_force_closes_live_connections(), Any, Return a plain `dict`, never a string — serialization belongs to the transport…, Mint a fresh envelope: new ULID `id`, current-time `ts`. Convenience for…

### Community 25 - "Pairing Code Minting"
Cohesion: 0.22
Nodes (15): pair_new(), Mint a pairing code and return it in plaintext. There is no control-plane verb…, consume_pairing_code(), _hash_code(), mint_pairing_code(), Connection, _random_code(), Pairing-code minting and atomic consumption (FR-11, §4.1). Minting is operator-… (+7 more)

### Community 26 - "Wire Message Ack/Heartbeat/Progress"
Cohesion: 0.16
Nodes (8): Ack, Heartbeat, ProgressMsg, Any, Either direction's `ack` frame. Empty payload — the envelope's `corr` carries…, Node → Bridge. Declared per HDP-0.md §2; no M1 producer or consumer., Either direction. Application-level heartbeat, belt-and-suspenders on top of…, _require_dict()

### Community 27 - "Plugin Engine Invoke Tests"
Cohesion: 0.29
Nodes (12): InvokeResult, The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is…, _device(), _FakeRuntime, _FakeTransport, _patched(), `engine.invoke()`'s resolution tree against a fake `BridgeTransport` — no…, test_invoke_propagates_transport_error() (+4 more)

### Community 28 - "Node Auth Failure & Fault Injection"
Cohesion: 0.17
Nodes (15): ClientWebSocketResponse, FaultConfig, AuthFailed, Exception, The bridge rejected this node's credential. Deliberately **not** an `OSError`…, parametrize, Finding I7.1: `Path.write_text` created this file at the process umask —…, `O_CREAT`'s mode argument is ignored when the file already exists — which is… (+7 more)

### Community 29 - "Bridge Daemon Profile Config"
Cohesion: 0.23
Nodes (14): bridge_addr_path(), control_socket_path(), hdp_home(), hermes_home(), pid_path(), Path, Profile-scoped paths, timeouts, and defaults for the standalone `hdp-bridge`…, The active Hermes profile's state root. Read fresh on every call — never cache… (+6 more)

### Community 30 - "Device Credential Issuance"
Cohesion: 0.29
Nodes (14): _hash(), issue_credential(), Connection, Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)., Returns the credential in plaintext. The caller (the `hello` handler, or `pair…, Returns the device_id the credential belongs to, or None if it matches no live…, Returns the number of live credentials this call actually invalidated. Zero…, revoke_credential() (+6 more)

### Community 31 - "Invocation Revocation Failure"
Cohesion: 0.17
Nodes (11): DeviceDisconnected, Exception, Set as the exception on whichever future (ack or result) is still pending when…, Connection, Returns the number of live credentials actually invalidated — `0` for an…, revoke_device(), _FakeWS, Operator-initiated revocation (FR-15, §4.4) — the four-step order enforced in… (+3 more)

### Community 32 - "Plugin Async Tool Handlers"
Cohesion: 0.22
Nodes (14): _echo(), _handler(), _notifications_send(), Any, T, The three async tool handlers. Every handler has the same shape (FR-1): `async…, `check_fn` for `device_notifications_send` and `hdp_echo`. Per ADR-0003,…, Wrap `fn` (which returns a *parsed* model-facing result dict, or raises) into a… (+6 more)

### Community 33 - "Reference Node Connect & Backoff"
Cohesion: 0.22
Nodes (11): The node-side second enforcement point (docs/design.md §4). Trivial at M1:…, _backoff_delay(), _connect_and_serve(), Path, The reference node: connects to an HDP bridge over WebSocket, advertises its…, FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based. The 30s ceiling…, Write the bridge-issued credential 0600, with no world-readable window at any…, Connect, advertise, dispatch forever, reconnecting with exponential backoff on… (+3 more)

### Community 34 - "Typed Wire Message Dataclasses"
Cohesion: 0.18
Nodes (8): ErrorMsg, Typed payload dataclasses for each HDP/0 message type (hdp-spec/HDP-0.md §2).…, Either direction. Same shape `hdp_proto.errors.err()` produces for the model-…, Bridge → Node. Declared per HDP-0.md §3.3; unused until M2's credential-…, _require_str(), _require_str_or_none(), RevokeMsg, test_hello_rejects_malformed_hdp_versions()

### Community 35 - "BridgeTransport Protocol & Approvals"
Cohesion: 0.14
Nodes (5): BridgeTransport, PendingApproval, Protocol, An HDP `pending_approval` state (seed §17). Unreachable at M0 — the stub never…, The eight operations `engine.py` and the plugin's diagnostics/status surface…

### Community 36 - "Reference Node CLI & Fault Flags"
Cohesion: 0.21
Nodes (8): build_parser(), _default_bridge_url(), main(), ArgumentParser, `hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect…, Fault injection for the conformance suite (m1-plan.md §7). Every fault is…, Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`., `python -m hdp_reference_node` entrypoint — equivalent to the `hdp-node`…

### Community 37 - "hermes hdp CLI Rendering Tests"
Cohesion: 0.21
Nodes (11): Calls `ctl_audit_tail` over the control socket rather than reading…, render_audit(), render_devices(), bridge_daemon(), fixture, `hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`,…, test_render_audit_against_a_real_daemon_contains_daemon_start(), test_render_audit_reports_unreachable_with_no_daemon() (+3 more)

### Community 38 - "Plugin Tool Registration Tests"
Cohesion: 0.21
Nodes (7): `register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on…, Task 17 / FR-18: two more renderers of the same underlying operations,…, D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side…, _RecordingCtx, test_register_also_registers_the_hdp_cli_command_and_slash_command(), test_register_does_not_spawn_the_hdp_runtime_thread(), test_register_registers_exactly_three_async_device_tools()

### Community 39 - "device_status_get Handler Tests"
Cohesion: 0.23
Nodes (11): _assert_structured_failure(), _clean_runtime_singleton(), fixture, parametrize, FR-1: every handler returns parseable JSON and never propagates an exception,…, `device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable…, FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}`…, test_device_status_get_succeeds_with_zero_nodes() (+3 more)

### Community 40 - "Devices Revoke CLI Fallback"
Cohesion: 0.25
Nodes (11): registry_db_path(), CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see…, render_devices_revoke(), No daemon reachable — `render_devices_revoke` falls back to the direct DB-only…, Finding I4, offline-fallback half: no live credential means nothing was…, Finding I4, live-daemon half: both CLIs used to `await read_frame(...)` and…, _register_device(), test_render_devices_revoke_against_a_real_daemon_reaches_the_control_socket() (+3 more)

### Community 41 - "hermes hdp CLI Entry Point"
Cohesion: 0.24
Nodes (10): _build_parser(), main(), ArgumentParser, `hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-…, The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here,…, CLI-only (finding I1) — `/hdp pair --new` no longer reaches this; see…, render_pair_new(), _run() (+2 more)

### Community 42 - "Plugin Engine & Tool Schemas"
Cohesion: 0.20
Nodes (8): invoke(), _policy_check_stub(), Any, `invoke()` — the one path every device tool shares (design §2.3). Ten numbered…, Step 4's call site — the allow-all stub, present from day one (design §2.3)…, Resolve a device, check policy, invoke, and return the model-facing JSON result…, Hermes Device Plugin package. `register(ctx)` below, plus `cli.py` and…, LLM-facing tool schemas — plain dicts, imported by nothing else in this…

### Community 43 - "Bridge Bind Host/Port Config"
Cohesion: 0.20
Nodes (10): Event, hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), The host the aiohttp node-facing server binds to. Read fresh on every call…, The port the aiohttp node-facing server binds to. `0` (test convention)…, NFR-4's guard: binding to a non-loopback host is refused unless this is set., main() (+2 more)

### Community 44 - "Daemon PID Claim Guard"
Cohesion: 0.24
Nodes (9): AlreadyRunningError, _check_and_claim_pid(), _pid_is_live(), RuntimeError, `hdp-bridge serve` — the foreground daemon entrypoint (§5.5). PID-file…, Another live hdp-bridge process already holds this profile's PID file., Treat `pid_path` as a *claim* to verify, not a fact to trust. If it names a…, A `bridge.pid` file that isn't a parseable integer (corrupted, truncated, ...)… (+1 more)

### Community 45 - "Daemon Serve Bind Failure Tests"
Cohesion: 0.31
Nodes (9): serve(), A partial-bind failure (`hdp_server.start()` succeeds, `control.start()`…, The PID claim happens before *any* binding. A failure anywhere between the…, _read_audit_records(), test_serve_binds_control_socket_and_writes_pid(), test_serve_cleans_up_a_stale_pid_from_a_dead_process(), test_serve_refuses_to_start_when_a_live_process_holds_the_pid_file(), test_serve_tears_down_node_socket_if_control_bind_fails() (+1 more)

### Community 46 - "Operator Revoke Orchestration"
Cohesion: 0.28
Nodes (7): HDP bridge daemon package., _error_detail(), Operator-surface orchestration, owned by `hdp_bridge` and shared by both…, Revoke `device_id`, returning the line the caller should render. Prefers the…, Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if…, revoke(), _revoke_via_control_socket()

### Community 47 - "Registry Schema Tables"
Cohesion: 0.28
Nodes (8): approvals, capabilities, credentials, devices, invocations, pairing_codes, policy_grants, schema_version

### Community 48 - "Bridge Server Wire-Level Tests"
Cohesion: 0.25
Nodes (4): _connect_and_hello(), Direct wire-level tests for `hdp_bridge.server` — a fake "node" is a raw…, test_hello_welcome_handshake_registers_the_device(), test_malformed_frame_gets_an_error_reply_and_stays_open()

### Community 49 - "HDP Envelope & Version Errors"
Cohesion: 0.28
Nodes (8): EnvelopeError, ValueError, The HDP/0 envelope: `{"hdp", "type", "id", "ts", "corr", "payload"}` — see…, Raised by `Envelope.from_wire` on any structurally or semantically invalid…, The frame's `hdp` field names a version we do not speak. Per HDP-0.md §3, this…, The frame's `type` field is missing or not in `KNOWN_TYPES`. Per HDP-0.md §5,…, UnknownTypeError, UnsupportedVersionError

### Community 50 - "ResultMsg Wire Round-Trip"
Cohesion: 0.28
Nodes (6): Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like…, ResultMsg, parametrize, test_from_wire_tolerates_unknown_fields(), test_result_msg_rejects_non_bool_ok(), test_round_trip()

### Community 51 - "InvokeMsg Wire Contract"
Cohesion: 0.32
Nodes (5): _InvokeRequestLike, Protocol, InvokeMsg, Bridge → Node. `corr` (on the envelope, not here) carries the bridge-minted…, test_invoke_msg_rejects_missing_deadline()

### Community 52 - "Capabilities Message Wire Format"
Cohesion: 0.33
Nodes (5): CapabilityDescriptor, One entry in a `capabilities` message's full-replacement list (HDP-0.md §2, §6)., _capabilities_from_wire(), CapabilitiesMsg, Either direction's `capabilities` frame: a full-set replacement, never a delta…

### Community 53 - "errors.md Conformance Tests"
Cohesion: 0.43
Nodes (6): _parse_errors_md(), FR-32: `hdp-spec/errors.md` (the normative doc) must be identical to…, Catches the inverse drift: a code declared in errors.md but removed from…, test_errors_md_code_set_and_order_match_error_code(), test_errors_md_has_no_orphaned_entries(), test_errors_md_hints_match_hints_dict()

### Community 54 - "hermes hdp Command Registration"
Cohesion: 0.29
Nodes (7): Any, Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement…, register_cli_command(), Any, Register the three device tools in toolset `device`, all `is_async=True`…, register(), test_register_cli_command_registers_hdp()

### Community 55 - "Welcome Message Credential Field"
Cohesion: 0.40
Nodes (4): Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is…, _require_int(), Welcome, test_welcome_credential_defaults_to_none_and_round_trips_present_as_null()

### Community 56 - "CancelMsg Best-Effort Send"
Cohesion: 0.40
Nodes (3): Best-effort — HDP-0.md §7: the caller has already removed the pending-table…, CancelMsg, Bridge → Node, sent best-effort on timeout or explicit cancellation.

### Community 57 - "uv Workspace Package Manifests"
Cohesion: 0.80
Nodes (5): hdp-bridge, hdp-proto, hdp-reference-node, hermes-device-plugin, hermes-device-protocol

### Community 58 - "device.status@1 Reference Handler"
Cohesion: 0.50
Nodes (3): handle(), Any, `device.status@1` (hdp-spec/capabilities/device.status@1.md). Deliberately…

### Community 59 - "diagnostics.echo@1 Reference Handler"
Cohesion: 0.50
Nodes (3): handle(), Any, `diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure…

### Community 60 - "notifications.send@1 Reference Handler"
Cohesion: 0.50
Nodes (3): handle(), Any, `notifications.send@1` (hdp-spec/capabilities/notifications.send@1.md). Prints…

### Community 61 - "hermes hdp status Rendering"
Cohesion: 0.50
Nodes (4): render_status(), test_render_status_reports_healthy_against_a_real_daemon(), test_render_status_reports_unreachable_with_no_daemon(), test_hdp_status_delegates_to_render_status()

### Community 62 - "Plugin Test Fixtures"
Cohesion: 0.50
Nodes (3): _hermes_home(), fixture, Test-wide fixtures for `hermes_device_plugin`. Real Hermes always sets…

### Community 63 - "Repo Scaffold Sanity Test"
Cohesion: 0.50
Nodes (3): Scaffold sanity tests., Keep `pytest` green before milestone implementation tests are added., test_scaffold_exists()

### Community 64 - "Control Socket Test Fixtures"
Cohesion: 0.67
Nodes (3): ctl_conn(), node_client(), fixture

## Knowledge Gaps
- **25 isolated node(s):** `schema_version`, `pairing_codes`, `policy_grants`, `approvals`, `invocations` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SocketTransport` connect `Socket Transport Client Tests` to `M2 Conformance Test Harness`, `BridgeTransport Protocol & Approvals`, `hermes hdp CLI Rendering Tests`, `Bridge Transport Base & Status`, `hermes hdp CLI Entry Point`, `HDP Runtime Event Loop`, `Bridge Socket Transport Client`, `HDP Error Envelope Helpers`, `HDP Envelope & Version Errors`, `HDPRuntime Singleton`, `Frame Handler Dispatch (Node/Bridge)`, `Plugin Engine Invoke Tests`, `hermes hdp status Rendering`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `Envelope` connect `Frame Handler Dispatch (Node/Bridge)` to `Bridge Node Connection Handling`, `Control Plane Frame Dispatch`, `ULID Minting & Parsing`, `Bridge Transport Base & Status`, `Socket Transport Client Tests`, `Bridge Control Server`, `Bridge Socket Transport Client`, `Operator Revoke Orchestration`, `HDP Envelope & Version Errors`, `InvokeMsg Wire Contract`, `Bridge Hello Auth Branch Tests`, `Control Verb Handlers & Cancel`, `Node Auth Failure & Fault Injection`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `NodeConnection` connect `Bridge Node Connection Handling` to `Control Plane Frame Dispatch`, `In-Memory Invocation Tracking`, `Bridge Control Server`, `Bridge Server Bind Lifecycle`, `Bridge aiohttp App & Health`, `Audit Log & Revocation`, `Bridge Hello Auth Branch Tests`, `Frame Handler Dispatch (Node/Bridge)`, `Invocation Revocation Failure`, `Typed Wire Message Dataclasses`, `Bridge Bind Host/Port Config`, `Daemon PID Claim Guard`, `Bridge Server Wire-Level Tests`, `HDP Envelope & Version Errors`, `ResultMsg Wire Round-Trip`, `InvokeMsg Wire Contract`, `Capabilities Message Wire Format`, `Welcome Message Credential Field`, `CancelMsg Best-Effort Send`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `NodeConnection` (e.g. with `AuditWriter` and `InvocationsMem`) actually correct?**
  _`NodeConnection` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `InvocationsMem` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`InvocationsMem` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Registry` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Registry` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Envelope` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Envelope` has 15 INFERRED edges - model-reasoned connections that need verification._