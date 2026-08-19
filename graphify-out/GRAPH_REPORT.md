# Graph Report - hermes-device-protocol  (2026-08-19)

## Corpus Check
- 107 files · ~51,392 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1221 nodes · 2789 edges · 80 communities (64 shown, 16 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 200 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `441b770c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Registry
- M2 Status (registry, pairing, bridge extraction)
- test_faults.py
- .new
- InvocationsMem
- socket.py
- InprocTransport
- test_transport_socket.py
- ControlServer
- test_plugin_commands.py
- HDPRuntime
- SocketTransport
- connect
- CapabilityDescriptor
- NodeConnection
- err
- server.py
- hermes_device_plugin/config.py
- test_server.py
- AuditWriter
- get_runtime
- Hello
- test_node_auth.py
- Envelope
- ._read_loop
- AuthFailed
- Ack
- InvokeResult
- FaultConfig
- hdp_bridge/config.py
- test_cli.py
- _InvokeReq
- tools.py
- node.py
- Any
- BridgeTransport
- hdp_reference_node/cli.py
- test_repeated_runtime_start_stop_does_not_leak_fds_or_threads
- _RecordingCtx
- test_tools.py
- test_plugin_cli.py
- hermes_device_plugin/cli.py
- engine.py
- daemon.py
- ._ctl_invoke
- test_daemon.py
- operations.py
- 001_initial.sql
- runtime.py
- envelope.py
- test_messages.py
- InvokeMsg
- Heartbeat
- ErrorCode
- hermes_device_plugin/__init__.py
- Welcome
- CancelMsg
- hdp-proto
- device_status.py
- diagnostics.py
- notifications.py
- render_status
- tests/conftest.py
- test_scaffold.py
- ._ctl_devices_revoke
- ApprovalManager
- policy.py
- capabilities/__init__.py
- Malformed and Out-of-Sequence Frame Handling
- transport/__init__.py
- ambiguous_device error code
- approval_denied error code
- approval_timeout error code
- bridge_unavailable error code
- capability_unsupported error code
- no_matching_device error code
- not_implemented error code
- policy_denied error code
- version_incompatible error code
- Binary Payload Rule (metadata in JSON, binary by content ID, no base64-in-envelope)

## God Nodes (most connected - your core abstractions)
1. `NodeConnection` - 73 edges
2. `InvocationsMem` - 66 edges
3. `Registry` - 66 edges
4. `Envelope` - 54 edges
5. `SocketTransport` - 51 edges
6. `ControlServer` - 49 edges
7. `AuditWriter` - 42 edges
8. `connect()` - 42 edges
9. `DeviceRecord` - 28 edges
10. `CapabilityDescriptor` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Dependency Direction Rule (protocol independent, plugin may depend on bridge, bridge must not import plugin)` --semantically_similar_to--> `Deviation: two SQLite connections in daemon.py, not one`  [INFERRED] [semantically similar]
  AGENTS.md → README.md
- `_register_device()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_devices_revoke_against_a_real_daemon_reaches_the_control_socket()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_devices_revoke_of_an_unknown_device_reports_no_such_device()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_devices_revoke_offline_fallback_records_via_marker()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py

## Import Cycles
- 3-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 4-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 5-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`

## Hyperedges (group relationships)
- **HDP Closed Error-Code Taxonomy Members** — hdp_spec_errors_taxonomy, hdp_spec_errors_bridge_unavailable, hdp_spec_errors_not_implemented, hdp_spec_errors_no_matching_device, hdp_spec_errors_capability_unsupported, hdp_spec_errors_ambiguous_device, hdp_spec_errors_device_offline, hdp_spec_errors_invocation_timeout, hdp_spec_errors_malformed_result, hdp_spec_errors_version_incompatible, hdp_spec_errors_auth_failed, hdp_spec_errors_policy_denied, hdp_spec_errors_approval_denied, hdp_spec_errors_approval_timeout, hdp_spec_errors_revoked, hdp_spec_errors_late_result, hdp_spec_errors_schema_drift [EXTRACTED 0.95]
- **Three MVP HDP Capabilities Advertised by Reference Node** — hdp_spec_capabilities_device_status_1, hdp_spec_capabilities_diagnostics_echo_1, hdp_spec_capabilities_notifications_send_1, hdp_spec_hdp_0_capability_descriptors [EXTRACTED 0.95]
- **hermes-device Plugin Tools Provided by plugin.yaml** — hermes_device_plugin_hermes_device_plugin_plugin_yaml_manifest, hermes_device_plugin_tool_device_notifications_send, hermes_device_plugin_tool_device_status_get, hermes_device_plugin_tool_hdp_echo [EXTRACTED 0.95]

## Communities (80 total, 16 thin omitted)

### Community 0 - "Registry"
Cohesion: 0.11
Nodes (28): _InvokeRequestLike, Protocol, Per-connection lifecycle for one node's WebSocket. One `NodeConnection` per…, Plugin↔bridge Unix-socket control plane (ADR-0004, HDP-0.md §2's "same…, Path, SQLite-backed device registry (§3, §3.1). `online` state is never persisted —…, No pairing exists yet (M2 pairing work) — a device enters this table only by…, Insert-or-replace the device row and fully replace its capability set (FR-8's… (+20 more)

### Community 1 - "M2 Status (registry, pairing, bridge extraction)"
Cohesion: 0.06
Nodes (42): Dependency Direction Rule (protocol independent, plugin may depend on bridge, bridge must not import plugin), make check (lint, format, typecheck, tests), Repository Guidelines (AGENTS.md), Working Style (CLAUDE.md), CI Workflow (make check), device.status@1 capability, device.status@1 is deliberately not what device_status_get calls, diagnostics.echo@1 capability (+34 more)

### Community 2 - "test_faults.py"
Cohesion: 0.10
Nodes (38): Process, bridge(), bridge_log(), _bridge_proc(), bridge_url(), _hermes_home(), fixture, Shared fixtures for the M2 conformance suite (m1-plan.md §7, m2-plan.md). HDP… (+30 more)

### Community 3 - ".new"
Cohesion: 0.11
Nodes (50): read_frame(), write_frame(), Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if…, _revoke_via_control_socket(), _connect_and_hello(), ctl_conn(), _ctl_invoke(), _ctl_invoke_envelope() (+42 more)

### Community 4 - "InvocationsMem"
Cohesion: 0.07
Nodes (30): InvocationsMem, PendingInvocation, Any, The bridge-side pending-invocation table — id → in-flight state. Backs real…, Fail every pending invocation regardless of device — used on transport shutdown…, A device's connection dropped (or was revoked): fail every invocation still…, Remove and fail every pending entry (all of them when `device_id` is `None`).…, Tracks in-flight invocations. Empty by construction; entries live only between… (+22 more)

### Community 5 - "socket.py"
Cohesion: 0.18
Nodes (12): BridgeStatus, CapabilityInfo, DeviceInfo, PendingApproval, `BridgeTransport` — the ADR-0004 extraction seam. `engine.py` depends on this…, An HDP `pending_approval` state (seed §17). Unreachable at M0 — the stub never…, _LoopbackInvocations, _LoopbackRegistry (+4 more)

### Community 6 - "InprocTransport"
Cohesion: 0.14
Nodes (10): InprocTransport, PendingApproval, Implements `BridgeTransport` (verified structurally by the tests, not by…, Real at M0: this is what `HDPRuntime` calls on its owned loop, and the shape…, The M0 loopback stub in isolation — no server, no socket, no node (design §6.4)., test_device_info_carries_fr13_fields_with_safe_defaults(), test_invoke_round_trips_through_the_real_codec_and_succeeds(), test_list_devices_is_empty_at_m0() (+2 more)

### Community 7 - "test_transport_socket.py"
Cohesion: 0.15
Nodes (22): InvokeRequest, One capability invocation, fully resolved by `engine.py` before it reaches the…, bridge_daemon(), fake_control_server(), _FakeControlServer, _invoke_request(), fixture, `SocketTransport` — the plugin-side client of `hdp_bridge/control.py`'s Unix-… (+14 more)

### Community 8 - "ControlServer"
Cohesion: 0.16
Nodes (13): ControlServer, _correlate(), _log_task_exception(), StreamReader, StreamWriter, `add_done_callback` hook for every fire-and-forget task this module spawns.…, Two independent mechanisms — not a poll loop guessing how many event-loop ticks…, Read loop for one control connection. `ctl_invoke` is dispatched *off* this… (+5 more)

### Community 9 - "test_plugin_commands.py"
Cohesion: 0.12
Nodes (22): handle_hdp_command(), Any, Hermes `/hdp status|devices|audit` slash command — the **read-only** half of…, `args` is accepted as either a raw string (split on whitespace here) or an…, Registers `/hdp` (design §2's confinement rule — this module is one of the…, register_command(), _hermes_home(), fixture (+14 more)

### Community 10 - "HDPRuntime"
Cohesion: 0.15
Nodes (9): AbstractEventLoop, HDPRuntime, Any, Future, T, Explicit teardown for tests (`lazy_singleton`'s `.reset()` only drops the…, Owns a daemon thread and the `asyncio` loop running on it. Constructed exactly…, `await self.transport.start()` runs to completion before anything checks… (+1 more)

### Community 11 - "SocketTransport"
Cohesion: 0.13
Nodes (11): PendingApproval, StreamWriter, Attempt to (re)connect. Must be called with `self._lock` held. Returns `True`…, Send one request and await its reply, holding no lock while waiting. The lock…, Operator-only verb, deliberately **not** on `BridgeTransport` — never reachable…, Implements `BridgeTransport` (verified structurally by the tests, not by…, Eagerly opens the connection once, matching…, SocketTransport (+3 more)

### Community 12 - "connect"
Cohesion: 0.08
Nodes (46): _hash(), issue_credential(), Connection, Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)., Returns the credential in plaintext. The caller (the `hello` handler, or `pair…, Returns the device_id the credential belongs to, or None if it matches no live…, Returns the number of live credentials this call actually invalidated. Zero…, revoke_credential() (+38 more)

### Community 13 - "CapabilityDescriptor"
Cohesion: 0.14
Nodes (21): CapabilityDescriptor, Any, ValueError, Capability descriptors and output-schema validation. `CapabilityDescriptor` is…, Raised by `validate_output` when `data` does not match `output_schema`. The…, One entry in a `capabilities` message's full-replacement list (HDP-0.md §2, §6)., Never `cls(**d)` — read fields by name, tolerate unknown fields, matching the…, Validate `data` against `descriptor.output_schema`. Raises… (+13 more)

### Community 14 - "NodeConnection"
Cohesion: 0.16
Nodes (7): NodeConnection, Started alongside `run()`'s own read loop and reaped in that same `finally`, on…, M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing…, Append now, drop anything outside the 60s window, and report whether the…, Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node…, _Harness, One `Registry`/`InvocationsMem`/`connections`/`descriptors` set, shared between…

### Community 15 - "err"
Cohesion: 0.13
Nodes (14): BaseException, Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call…, err(), Error, ok(), Any, The closed HDP error-code taxonomy and the model-facing result envelope.…, Build the failure half of the model-facing result envelope. `detail` becomes… (+6 more)

### Community 16 - "server.py"
Cohesion: 0.09
Nodes (32): Application, ConnectionFactory, _blobs_reserved(), _bound_port(), build_app(), HdpServer, _health(), _make_socket_handler() (+24 more)

### Community 17 - "hermes_device_plugin/config.py"
Cohesion: 0.14
Nodes (18): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), Path (+10 more)

### Community 18 - "test_server.py"
Cohesion: 0.13
Nodes (9): SQLite store helpers., client(), _connect_and_hello(), _Harness, fixture, Direct wire-level tests for `hdp_bridge.server` — a fake "node" is a raw…, The same shared-state wiring `EmbeddedTransport` used to own at M1: one…, test_hello_welcome_handshake_registers_the_device() (+1 more)

### Community 19 - "AuditWriter"
Cohesion: 0.08
Nodes (25): AuditWriter, Path, Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON…, Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb —…, Connection, WebSocketResponse, Connection, Path (+17 more)

### Community 20 - "get_runtime"
Cohesion: 0.18
Nodes (14): get_runtime(), The one `HDPRuntime` for this process, built at first use. Do not call this…, `check_fn` for `device_notifications_send` and `hdp_echo`. Per ADR-0003,…, runtime_healthy(), _clean_runtime_singleton(), fixture, The real M0 deliverable (docs/m0-plan.md §6.5): `HDPRuntime` called from all…, Every test starts and ends with no HDP thread alive, so leak assertions are… (+6 more)

### Community 21 - "Hello"
Cohesion: 0.24
Nodes (11): _FakeWS, `_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired…, _read_audit_records(), test_hello_with_a_returning_credential_resolves_the_same_device_id(), test_hello_with_a_revoked_credential_is_auth_failed(), test_hello_with_a_valid_pairing_code_pairs_and_returns_a_credential(), test_hello_with_an_invalid_pairing_code_is_auth_failed(), test_hello_with_an_unknown_credential_is_auth_failed() (+3 more)

### Community 22 - "test_node_auth.py"
Cohesion: 0.15
Nodes (13): AppRunner, _abrupt_close_handler(), _auth_failed_handler(), bridge_stub(), _pairing_handler(), fixture, The reference node's M2 auth behaviour (final-review findings I7 and I8).…, Completes a first-time pairing and issues a credential, then holds the socket… (+5 more)

### Community 23 - "Envelope"
Cohesion: 0.14
Nodes (9): Operator-only verb (`hermes hdp devices` at Task 17 was ultimately built…, Return daemon-memory approvals; none are durable while pending., _NodeSession, Any, Per-connection dispatch state: which invocation ids have been cancelled by the…, M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a…, Envelope, Return a plain `dict`, never a string — serialization belongs to the transport… (+1 more)

### Community 24 - "._read_loop"
Cohesion: 0.40
Nodes (5): _bridge_unavailable(), Future, StreamReader, Demultiplex every reply on one connection into the future that is waiting for…, _read_frame()

### Community 25 - "AuthFailed"
Cohesion: 0.40
Nodes (5): AuthFailed, Exception, The bridge rejected this node's credential. Deliberately **not** an `OSError`…, Finding I7.3, the whole bug in one line: the old code raised `ConnectionError`,…, test_auth_failed_is_terminal_and_never_retried()

### Community 27 - "InvokeResult"
Cohesion: 0.29
Nodes (12): InvokeResult, The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is…, _device(), _FakeRuntime, _FakeTransport, _patched(), `engine.invoke()`'s resolution tree against a fake `BridgeTransport` — no…, test_invoke_propagates_transport_error() (+4 more)

### Community 28 - "FaultConfig"
Cohesion: 0.14
Nodes (14): ClientWebSocketResponse, FaultConfig, Fault injection for the conformance suite (m1-plan.md §7). Every fault is…, Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`., parametrize, Finding I7.1: `Path.write_text` created this file at the process umask —…, `O_CREAT`'s mode argument is ignored when the file already exists — which is…, Finding I7.2: `revoke` used to be a documented no-op ("no action needed ... at… (+6 more)

### Community 29 - "hdp_bridge/config.py"
Cohesion: 0.20
Nodes (17): bridge_addr_path(), control_socket_path(), hdp_home(), hermes_home(), pid_path(), policy_path(), Path, Profile-scoped paths, timeouts, and defaults for the standalone `hdp-bridge`… (+9 more)

### Community 30 - "test_cli.py"
Cohesion: 0.17
Nodes (17): main(), Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback…, _run_audit_tail(), _run_devices_revoke(), _run_pair_new(), _insert_device_with_credential(), `hdp-bridge` CLI — `pair new`'s audit call site (Task 16) and `audit tail`. No…, Finding I4: the offline fallback used to print "revoked <id>" unconditionally,… (+9 more)

### Community 31 - "_InvokeReq"
Cohesion: 0.16
Nodes (11): _InvokeReq, Satisfies `connection.py`'s `_InvokeRequestLike` `Protocol` — `ctl_invoke`'s…, DeviceDisconnected, Exception, Set as the exception on whichever future (ack or result) is still pending when…, _FakeWS, Presence (FR-16) — heartbeat-driven `last_seen_at` and 45s dead-peer detection.…, The dead-peer monitor drives an ordinary disconnect, not a revocation.… (+3 more)

### Community 32 - "tools.py"
Cohesion: 0.27
Nodes (12): _echo(), _handler(), _notifications_send(), Any, T, The three async tool handlers. Every handler has the same shape (FR-1): `async…, Wrap `fn` (which returns a *parsed* model-facing result dict, or raises) into a…, Run `coro` on the HDP loop and await its answer on *the caller's* loop. The two… (+4 more)

### Community 33 - "node.py"
Cohesion: 0.22
Nodes (11): The node-side second enforcement point (docs/design.md §4). Trivial at M1:…, _backoff_delay(), _connect_and_serve(), Path, The reference node: connects to an HDP bridge over WebSocket, advertises its…, FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based. The 30s ceiling…, Write the bridge-issued credential 0600, with no world-readable window at any…, Connect, advertise, dispatch forever, reconnecting with exponential backoff on… (+3 more)

### Community 34 - "Any"
Cohesion: 0.14
Nodes (15): _capabilities_from_wire(), CapabilitiesMsg, ErrorMsg, ProgressMsg, Any, Typed payload dataclasses for each HDP/0 message type (hdp-spec/HDP-0.md §2).…, Either direction's `capabilities` frame: a full-set replacement, never a delta…, Node → Bridge. Declared per HDP-0.md §2; no M1 producer or consumer. (+7 more)

### Community 35 - "BridgeTransport"
Cohesion: 0.18
Nodes (3): BridgeTransport, Protocol, The eight operations `engine.py` and the plugin's diagnostics/status surface…

### Community 36 - "hdp_reference_node/cli.py"
Cohesion: 0.27
Nodes (7): build_parser(), _default_bridge_url(), main(), ArgumentParser, `hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect…, Python HDP reference node package., `python -m hdp_reference_node` entrypoint — equivalent to the `hdp-node`…

### Community 37 - "test_repeated_runtime_start_stop_does_not_leak_fds_or_threads"
Cohesion: 0.33
Nodes (8): skipif, _fd_count(), _hdp_thread_count(), M1-1's risk mitigation (m1-plan.md §9): the embedded aiohttp server's…, `HDPRuntime.close()` already blocks on `Thread.join()`, but the loop thread…, test_repeated_runtime_start_stop_does_not_leak_fds_or_threads(), _wait_for_no_hdp_threads(), timeout

### Community 38 - "_RecordingCtx"
Cohesion: 0.21
Nodes (7): `register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on…, Task 17 / FR-18: two more renderers of the same underlying operations,…, D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side…, _RecordingCtx, test_register_also_registers_the_hdp_cli_command_and_slash_command(), test_register_does_not_spawn_the_hdp_runtime_thread(), test_register_registers_exactly_three_async_device_tools()

### Community 39 - "test_tools.py"
Cohesion: 0.23
Nodes (11): _assert_structured_failure(), _clean_runtime_singleton(), fixture, parametrize, FR-1: every handler returns parseable JSON and never propagates an exception,…, `device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable…, FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}`…, test_device_status_get_succeeds_with_zero_nodes() (+3 more)

### Community 40 - "test_plugin_cli.py"
Cohesion: 0.16
Nodes (17): CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see…, render_devices(), render_devices_revoke(), bridge_daemon(), fixture, `hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`,…, No daemon reachable — `render_devices_revoke` falls back to the direct DB-only…, Finding I4, offline-fallback half: no live credential means nothing was… (+9 more)

### Community 41 - "hermes_device_plugin/cli.py"
Cohesion: 0.16
Nodes (18): _build_parser(), main(), ArgumentParser, `hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-…, Calls `ctl_audit_tail` over the control socket rather than reading…, The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here,…, CLI-only (finding I1) — `/hdp pair --new` no longer reaches this; see…, render_approvals() (+10 more)

### Community 42 - "engine.py"
Cohesion: 0.33
Nodes (6): invoke(), _policy_check_stub(), Any, `invoke()` — the one path every device tool shares (design §2.3). Ten numbered…, Step 4's call site — the allow-all stub, present from day one (design §2.3)…, Resolve a device, check policy, invoke, and return the model-facing JSON result…

### Community 43 - "daemon.py"
Cohesion: 0.13
Nodes (19): Event, hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), The host the aiohttp node-facing server binds to. Read fresh on every call…, The port the aiohttp node-facing server binds to. `0` (test convention)…, NFR-4's guard: binding to a non-loopback host is refused unless this is set., AlreadyRunningError (+11 more)

### Community 44 - "._ctl_invoke"
Cohesion: 0.29
Nodes (6): _approval_args_summary(), _invoke_failure(), Any, The plugin-reachable half of the ack-timeout/execution-deadline race — a…, A failed `ctl_invoke_reply`, mirroring `embedded.py`'s `_failure` helper.…, Render approval-safe arguments without ever putting raw values into SQLite or…

### Community 45 - "test_daemon.py"
Cohesion: 0.24
Nodes (11): serve(), A partial-bind failure (`hdp_server.start()` succeeds, `control.start()`…, The PID claim happens before *any* binding. A failure anywhere between the…, A `bridge.pid` file that isn't a parseable integer (corrupted, truncated, ...)…, _read_audit_records(), test_check_and_claim_pid_treats_a_malformed_pid_file_as_no_claim(), test_serve_binds_control_socket_and_writes_pid(), test_serve_cleans_up_a_stale_pid_from_a_dead_process() (+3 more)

### Community 46 - "operations.py"
Cohesion: 0.20
Nodes (9): HDP bridge daemon package., _error_detail(), pair_new(), Operator-surface orchestration, owned by `hdp_bridge` and shared by both…, Mint a pairing code and return it in plaintext. There is no control-plane verb…, True when `revoke()`'s return value describes a failure rather than a completed…, Revoke `device_id`, returning the line the caller should render. Prefers the…, revoke() (+1 more)

### Community 47 - "001_initial.sql"
Cohesion: 0.28
Nodes (8): approvals, capabilities, credentials, devices, invocations, pairing_codes, policy_grants, schema_version

### Community 48 - "runtime.py"
Cohesion: 0.40
Nodes (4): `HDPRuntime` — the pattern the whole architecture bets on (ADR-0002,…, lazy_singleton(), T, Stdlib fallback for `plugins.plugin_utils.lazy_singleton`, used only when no…

### Community 49 - "envelope.py"
Cohesion: 0.08
Nodes (40): EnvelopeError, ValueError, The HDP/0 envelope: `{"hdp", "type", "id", "ts", "corr", "payload"}` — see…, Raised by `Envelope.from_wire` on any structurally or semantically invalid…, The frame's `hdp` field names a version we do not speak. Per HDP-0.md §3, this…, The frame's `type` field is missing or not in `KNOWN_TYPES`. Per HDP-0.md §5,…, UnknownTypeError, UnsupportedVersionError (+32 more)

### Community 50 - "test_messages.py"
Cohesion: 0.24
Nodes (6): Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like…, ResultMsg, parametrize, test_from_wire_tolerates_unknown_fields(), test_result_msg_rejects_non_bool_ok(), test_round_trip()

### Community 51 - "InvokeMsg"
Cohesion: 0.33
Nodes (4): InvokeMsg, Bridge → Node. `corr` (on the envelope, not here) carries the bridge-minted…, _require_int(), test_invoke_msg_rejects_missing_deadline()

### Community 53 - "ErrorCode"
Cohesion: 0.29
Nodes (9): ErrorCode, StrEnum, Stable declaration order — this is the order the M1 conformance test diffs…, _parse_errors_md(), FR-32: `hdp-spec/errors.md` (the normative doc) must be identical to…, Catches the inverse drift: a code declared in errors.md but removed from…, test_errors_md_code_set_and_order_match_error_code(), test_errors_md_has_no_orphaned_entries() (+1 more)

### Community 54 - "hermes_device_plugin/__init__.py"
Cohesion: 0.18
Nodes (9): Any, Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement…, register_cli_command(), Any, Hermes Device Plugin package. `register(ctx)` below, plus `cli.py` and…, Register the three device tools in toolset `device`, all `is_async=True`…, register(), LLM-facing tool schemas — plain dicts, imported by nothing else in this… (+1 more)

### Community 55 - "Welcome"
Cohesion: 0.40
Nodes (4): _revoking_handler(), Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is…, Welcome, test_welcome_credential_defaults_to_none_and_round_trips_present_as_null()

### Community 56 - "CancelMsg"
Cohesion: 0.33
Nodes (3): Best-effort — HDP-0.md §7: the caller has already removed the pending-table…, CancelMsg, Bridge → Node, sent best-effort on timeout or explicit cancellation.

### Community 57 - "hdp-proto"
Cohesion: 0.80
Nodes (5): hdp-bridge, hdp-proto, hdp-reference-node, hermes-device-plugin, hermes-device-protocol

### Community 58 - "device_status.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `device.status@1` (hdp-spec/capabilities/device.status@1.md). Deliberately…

### Community 59 - "diagnostics.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure…

### Community 60 - "notifications.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `notifications.send@1` (hdp-spec/capabilities/notifications.send@1.md). Prints…

### Community 61 - "render_status"
Cohesion: 0.50
Nodes (4): render_status(), test_render_status_reports_healthy_against_a_real_daemon(), test_render_status_reports_unreachable_with_no_daemon(), test_hdp_status_delegates_to_render_status()

### Community 62 - "tests/conftest.py"
Cohesion: 0.50
Nodes (3): _hermes_home(), fixture, Test-wide fixtures for `hermes_device_plugin`. Real Hermes always sets…

### Community 63 - "test_scaffold.py"
Cohesion: 0.50
Nodes (3): Scaffold sanity tests., Keep `pytest` green before milestone implementation tests are added., test_scaffold_exists()

### Community 65 - "ApprovalManager"
Cohesion: 0.08
Nodes (27): ApprovalManager, ApprovalResolution, ApprovalScope, ApprovalState, PendingApproval, Connection, StrEnum, In-memory approval lifecycle with terminal SQLite decision records. (+19 more)

### Community 66 - "policy.py"
Cohesion: 0.08
Nodes (24): Decision, Mode, _NoDuplicateSafeLoader, PolicyEngine, PolicyTable, PolicyValidationError, Path, StrEnum (+16 more)

## Knowledge Gaps
- **25 isolated node(s):** `schema_version`, `pairing_codes`, `policy_grants`, `approvals`, `invocations` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Envelope` connect `Envelope` to `Registry`, `.new`, `socket.py`, `InprocTransport`, `test_transport_socket.py`, `ControlServer`, `SocketTransport`, `NodeConnection`, `err`, `test_server.py`, `Hello`, `._read_loop`, `AuthFailed`, `_InvokeReq`, `._ctl_invoke`, `operations.py`, `envelope.py`, `test_messages.py`, `._ctl_devices_revoke`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `InvocationsMem` connect `InvocationsMem` to `Registry`, `.new`, `ControlServer`, `daemon.py`, `connect`, `NodeConnection`, `test_server.py`, `AuditWriter`, `Hello`, `_InvokeReq`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `NodeConnection` connect `NodeConnection` to `Registry`, `.new`, `InvocationsMem`, `ControlServer`, `connect`, `CapabilityDescriptor`, `server.py`, `test_server.py`, `AuditWriter`, `Hello`, `Envelope`, `_InvokeReq`, `Any`, `daemon.py`, `envelope.py`, `test_messages.py`, `InvokeMsg`, `Welcome`, `CancelMsg`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `NodeConnection` (e.g. with `AuditWriter` and `InvocationsMem`) actually correct?**
  _`NodeConnection` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `InvocationsMem` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`InvocationsMem` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Registry` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Registry` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Envelope` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Envelope` has 15 INFERRED edges - model-reasoned connections that need verification._