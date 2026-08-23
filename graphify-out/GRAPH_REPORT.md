# Graph Report - hermes-device-protocol  (2026-08-22)

## Corpus Check
- 120 files · ~69,238 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1606 nodes · 4102 edges · 89 communities (71 shown, 18 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 351 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7b4e5790`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- render_status
- SocketTransport
- test_faults.py
- .new
- Registry
- test_seed_success_criterion.py
- server.py
- ApprovalManager
- ._handle
- .__init__
- control.py
- hdp_bridge/__init__.py
- InvokeRequest
- InvocationsMem
- test_node_auth.py
- ErrorCode
- test_m4_resolution.py
- AuditWriter
- .known_active_device_ids
- test_plugin_commands.py
- connect
- capabilities.py
- BridgeStatus
- _ResolvedTarget
- hermes_device_plugin/cli.py
- invoke
- test_plugin_cli.py
- hermes_device_plugin/config.py
- test_server.py
- node.py
- _serve_claimed
- CapabilityDescriptor
- test_repeated_runtime_start_stop_does_not_leak_fds_or_threads
- HDPRuntime
- PolicyTable
- issue_credential
- test_presence.py
- AndroidNodeFixture
- mint_pairing_code
- Capability Descriptors (name/version/input_schema/output_schema)
- daemon.py
- test_tools.py
- _NodeSession
- asyncio
- runtime.py
- InvokeResult
- _RecordingCtx
- test_node_cli.py
- test_device_bound_pairing.py
- M2 bridge extraction
- BridgeTransport
- Hello
- Repository Guidelines
- 001_initial.sql
- Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect)
- acceptance job
- Envelope
- register_cli_command
- NodeConnection
- hdp-proto
- bridge_stub
- build_app
- _backoff_delay
- Android Node Contract
- _ImmediateConnection
- test_connection_auth.py
- tests/conftest.py
- test_scaffold.py
- device_keys.py
- test_revocation.py
- _FakeWS
- capabilities/__init__.py
- Malformed and Out-of-Sequence Frame Handling
- transport/__init__.py
- PolicyEngine
- ambiguous_device error code
- approval_denied error code
- approval_timeout error code
- auth_failed error code
- bridge_unavailable error code
- capability_unsupported error code
- no_matching_device error code
- not_implemented error code
- policy_denied error code
- revoked error code
- version_incompatible error code
- Binary Payload Rule (metadata in JSON, binary by content ID, no base64-in-envelope)
- .__init__

## God Nodes (most connected - your core abstractions)
1. `Registry` - 98 edges
2. `NodeConnection` - 95 edges
3. `InvocationsMem` - 95 edges
4. `Envelope` - 76 edges
5. `connect()` - 72 edges
6. `ControlServer` - 66 edges
7. `Hello` - 55 edges
8. `CapabilityDescriptor` - 54 edges
9. `SocketTransport` - 54 edges
10. `DeviceRecord` - 48 edges

## Surprising Connections (you probably didn't know these)
- `_PendingHandshake` --uses--> `CapabilityDescriptor`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/capabilities.py
- `_PendingHandshake` --uses--> `Envelope`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/envelope.py
- `_PendingHandshake` --uses--> `EnvelopeError`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/envelope.py
- `_PendingHandshake` --uses--> `UnsupportedVersionError`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/envelope.py
- `_PendingHandshake` --uses--> `CancelMsg`  [INFERRED]
  hdp-bridge/hdp_bridge/connection.py → hdp-spec/hdp_proto/messages.py

## Import Cycles
- 3-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 4-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 5-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`

## Hyperedges (group relationships)
- **M2 Bridge Daemon Architecture** — readme_m2_bridge_extraction, agents_hdp_bridge, readme_sqlite_device_registry, readme_websocket_pairing, readme_control_plane [EXTRACTED 1.00]
- **HDP Closed Error-Code Taxonomy Members** — hdp_spec_errors_taxonomy, hdp_spec_errors_bridge_unavailable, hdp_spec_errors_not_implemented, hdp_spec_errors_no_matching_device, hdp_spec_errors_capability_unsupported, hdp_spec_errors_ambiguous_device, hdp_spec_errors_device_offline, hdp_spec_errors_invocation_timeout, hdp_spec_errors_malformed_result, hdp_spec_errors_version_incompatible, hdp_spec_errors_auth_failed, hdp_spec_errors_policy_denied, hdp_spec_errors_approval_denied, hdp_spec_errors_approval_timeout, hdp_spec_errors_revoked, hdp_spec_errors_late_result, hdp_spec_errors_schema_drift [EXTRACTED 0.95]
- **Three MVP HDP Capabilities Advertised by Reference Node** — hdp_spec_capabilities_device_status_1, hdp_spec_capabilities_diagnostics_echo_1, hdp_spec_capabilities_notifications_send_1, hdp_spec_hdp_0_capability_descriptors [EXTRACTED 0.95]
- **hermes-device Plugin Tools Provided by plugin.yaml** — hermes_device_plugin_hermes_device_plugin_plugin_yaml_manifest, hermes_device_plugin_tool_device_notifications_send, hermes_device_plugin_tool_device_status_get, hermes_device_plugin_tool_hdp_echo [EXTRACTED 0.95]

## Communities (89 total, 18 thin omitted)

### Community 0 - "render_status"
Cohesion: 0.50
Nodes (4): render_status(), test_render_status_reports_healthy_against_a_real_daemon(), test_render_status_reports_unreachable_with_no_daemon(), test_hdp_status_delegates_to_render_status()

### Community 1 - "SocketTransport"
Cohesion: 0.07
Nodes (39): _bridge_unavailable(), Future, PendingApproval, StreamReader, StreamWriter, Attempt to (re)connect. Must be called with `self._lock` held. Returns `True`…, Demultiplex every reply on one connection into the future that is waiting for…, Send one request and await its reply, holding no lock while waiting. The lock… (+31 more)

### Community 2 - "test_faults.py"
Cohesion: 0.06
Nodes (75): Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like…, ResultMsg, Process, bridge(), bridge_log(), _bridge_proc(), bridge_url(), external_node_mode() (+67 more)

### Community 3 - ".new"
Cohesion: 0.05
Nodes (89): read_frame(), write_frame(), control_request(), Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if…, Make one operator control-plane request without importing the plugin transport., _revoke_via_control_socket(), _connect_and_hello(), ctl_conn() (+81 more)

### Community 4 - "Registry"
Cohesion: 0.10
Nodes (38): _InvokeRequestLike, _PendingHandshake, Protocol, Per-connection lifecycle for one node's WebSocket. One `NodeConnection` per…, A challenge awaiting its proof (HDP-0.md Amendments v0.4). `pair_code` is set…, SQLite-backed device registry (§3, §3.1). `online` state is never persisted —…, No pairing exists yet (M2 pairing work) — a device enters this table only by…, Insert-or-replace the device row and fully replace its capability set (FR-8's… (+30 more)

### Community 5 - "test_seed_success_criterion.py"
Cohesion: 0.14
Nodes (34): acceptance, CompletedProcess, Popen, _acceptance_environment(), _assert_plugin_and_tools(), _chat(), _device_tool_count(), _hermes_command() (+26 more)

### Community 6 - "server.py"
Cohesion: 0.12
Nodes (20): _bound_port(), HdpServer, The standalone `hdp-bridge` daemon's aiohttp app (ADR-0004, design §3) — the M2…, `TCPSite` doesn't expose the bound port directly when the requested port was…, Owns the `AppRunner`/`TCPSite` pair and the `bridge.addr` discovery file., Bind and start serving. Returns the actually-bound port. Refuses to bind a non-…, _write_bridge_addr(), _noop_connection_factory() (+12 more)

### Community 7 - "ApprovalManager"
Cohesion: 0.08
Nodes (23): ApprovalManager, ApprovalResolution, PendingApproval, Connection, In-memory approval lifecycle with terminal SQLite decision records., Return a stable presentation order without exposing internal state., Resolve one pending approval and persist exactly one terminal outcome., Terminally expire every approval whose 120-second deadline has elapsed. (+15 more)

### Community 8 - "._handle"
Cohesion: 0.18
Nodes (11): _correlate(), _log_task_exception(), StreamReader, StreamWriter, Stamp `reply.corr` with the request envelope's `id`. Applied to *every* reply,…, `add_done_callback` hook for every fire-and-forget task this module spawns.…, Two independent mechanisms — not a poll loop guessing how many event-loop ticks…, Read loop for one control connection. `ctl_invoke` is dispatched *off* this… (+3 more)

### Community 10 - "control.py"
Cohesion: 0.10
Nodes (31): ApprovalScope, ApprovalState, StrEnum, Terminal approval outcomes persisted to the registry., The permitted scope choices for an approval decision., Raised when an approval is no longer pending., UnknownApprovalError, _InvokeReq (+23 more)

### Community 11 - "hdp_bridge/__init__.py"
Cohesion: 0.10
Nodes (31): _control_request(), main(), Path, Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback…, _run_approval_resolve(), _run_approvals_list(), _run_audit_tail(), _run_devices_revoke() (+23 more)

### Community 12 - "InvokeRequest"
Cohesion: 0.09
Nodes (22): DeviceInfo, InvokeRequest, PendingApproval, `BridgeTransport` — the ADR-0004 extraction seam. `engine.py` depends on this…, One unresolved capability invocation for daemon-side live resolution. Carries…, An HDP `pending_approval` state (seed §17). Unreachable at M0 — the stub never…, InprocTransport, _LoopbackInvocations (+14 more)

### Community 13 - "InvocationsMem"
Cohesion: 0.07
Nodes (32): InvocationsMem, Any, The bridge-side pending-invocation table — id → in-flight state. Backs real…, Called when a `result` frame arrives. Returns `False` for an unknown id — the…, Fail every pending invocation regardless of device — used on transport shutdown…, A device's connection dropped (or was revoked): fail every invocation still…, Fail only calls dispatched through one concrete connection generation., Remove and fail every pending entry (all of them when `device_id` is `None`).… (+24 more)

### Community 14 - "test_node_auth.py"
Cohesion: 0.14
Nodes (25): FaultConfig, Connect, advertise, dispatch forever, reconnecting with exponential backoff on…, run(), _abrupt_close_handler(), _auth_failed_handler(), _pairing_handler(), parametrize, The reference node's M2 auth behaviour (final-review findings I7 and I8).… (+17 more)

### Community 15 - "ErrorCode"
Cohesion: 0.18
Nodes (12): Error, ErrorCode, StrEnum, The closed HDP error-code taxonomy and the model-facing result envelope.…, Stable declaration order — this is the order the M1 conformance test diffs…, The `error` half of the model-facing result envelope., _parse_errors_md(), FR-32: `hdp-spec/errors.md` (the normative doc) must be identical to… (+4 more)

### Community 16 - "test_m4_resolution.py"
Cohesion: 0.17
Nodes (30): Validate decoded policy data and construct one immutable snapshot., _BlockingConnection, _capability(), _device(), _device_in_state(), _MemoryAudit, parametrize, _request() (+22 more)

### Community 17 - "AuditWriter"
Cohesion: 0.13
Nodes (17): AuditWriter, Path, Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON…, Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb —…, _error_detail(), Operator-surface orchestration, owned by `hdp_bridge` and shared by both…, Revoke `device_id`, returning the line the caller should render. Prefers the…, revoke() (+9 more)

### Community 19 - "test_plugin_commands.py"
Cohesion: 0.12
Nodes (22): handle_hdp_command(), Any, Hermes `/hdp status|devices|audit` slash command — the **read-only** half of…, `args` is accepted as either a raw string (split on whitespace here) or an…, Registers `/hdp` (design §2's confinement rule — this module is one of the…, register_command(), _hermes_home(), fixture (+14 more)

### Community 20 - "connect"
Cohesion: 0.12
Nodes (21): _apply_pragmas(), connect(), _migrate(), Connection, Path, RuntimeError, SQLite connection factory and forward-only migration runner (§3.1, §3.2)., The database's `schema_version` is higher than this build of `hdp_bridge` knows… (+13 more)

### Community 21 - "capabilities.py"
Cohesion: 0.09
Nodes (24): handle(), Any, `device.status@1` (hdp-spec/capabilities/device.status@1.md). Deliberately…, handle(), Any, `diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure…, handle(), Any (+16 more)

### Community 22 - "BridgeStatus"
Cohesion: 0.15
Nodes (20): capability_available(), _CapabilityAvailability, Lock-protected capability snapshot read synchronously by Hermes ``check_fn``…, Return the latest visibility hint without creating or contacting the runtime., Publish one complete live bridge sample (also the focused-test seam)., _reset_availability_for_tests(), _update_availability(), echo_available() (+12 more)

### Community 23 - "_ResolvedTarget"
Cohesion: 0.13
Nodes (17): _approval_args_summary(), _cancel_and_drain(), _invoke_failure(), Any, Future, _raise_if_cancelling(), A failed `ctl_invoke_reply`, mirroring `embedded.py`'s `_failure` helper.…, Render approval-safe arguments without ever putting raw values into SQLite or… (+9 more)

### Community 24 - "hermes_device_plugin/cli.py"
Cohesion: 0.15
Nodes (19): _build_parser(), main(), ArgumentParser, `hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-…, Calls `ctl_audit_tail` over the control socket rather than reading…, The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here,…, CLI-only (finding I1) — `/hdp pair --new` no longer reaches this; see…, render_approvals() (+11 more)

### Community 25 - "invoke"
Cohesion: 0.18
Nodes (15): invoke(), Any, Forward one unresolved request and return the daemon's model-facing result., _echo(), _handler(), _notifications_send(), Any, T (+7 more)

### Community 26 - "test_plugin_cli.py"
Cohesion: 0.16
Nodes (19): registry_db_path(), CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see…, render_devices(), render_devices_revoke(), bridge_daemon(), fixture, `hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`,…, No daemon reachable — `render_devices_revoke` falls back to the direct DB-only… (+11 more)

### Community 27 - "hermes_device_plugin/config.py"
Cohesion: 0.14
Nodes (18): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), Path (+10 more)

### Community 28 - "test_server.py"
Cohesion: 0.15
Nodes (8): client(), _connect_and_hello(), _Harness, fixture, Direct wire-level tests for `hdp_bridge.server` — a fake "node" is a raw…, The same shared-state wiring `EmbeddedTransport` used to own at M1: one…, test_hello_welcome_handshake_registers_the_device(), test_malformed_frame_gets_an_error_reply_and_stays_open()

### Community 29 - "node.py"
Cohesion: 0.18
Nodes (12): The node-side second enforcement point (docs/design.md §4). Trivial at M1:…, AuthFailed, _connect_and_serve(), Exception, Path, The reference node: connects to an HDP bridge over WebSocket, advertises its…, The bridge rejected this node's credential. Deliberately **not** an `OSError`…, Write the bridge-issued credential 0600, with no world-readable window at any… (+4 more)

### Community 30 - "_serve_claimed"
Cohesion: 0.13
Nodes (25): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), pid_path() (+17 more)

### Community 31 - "CapabilityDescriptor"
Cohesion: 0.08
Nodes (25): CapabilityDescriptor, ValueError, One entry in a `capabilities` message's full-replacement list (HDP-0.md §2, §6)., Never `cls(**d)` — read fields by name, tolerate unknown fields, matching the…, Ack, CancelMsg, _capabilities_from_wire(), ErrorMsg (+17 more)

### Community 32 - "test_repeated_runtime_start_stop_does_not_leak_fds_or_threads"
Cohesion: 0.33
Nodes (8): skipif, _fd_count(), _hdp_thread_count(), timeout, M1-1's risk mitigation (m1-plan.md §9): the embedded aiohttp server's…, `HDPRuntime.close()` already blocks on `Thread.join()`, but the loop thread…, test_repeated_runtime_start_stop_does_not_leak_fds_or_threads(), _wait_for_no_hdp_threads()

### Community 33 - "HDPRuntime"
Cohesion: 0.14
Nodes (10): AbstractEventLoop, HDPRuntime, Any, Future, T, `await self.transport.start()` runs to completion before anything checks…, Publish one bounded live sample, retaining the last hint when sampling fails. A…, Schedule `coro` onto the HDP loop from any thread. Returns a plain… (+2 more)

### Community 34 - "PolicyTable"
Cohesion: 0.20
Nodes (6): PolicyTable, Path, Resolve a device/capability pair using the documented four layers., Return this snapshot's configured target for one capability, if any., Capture the current immutable policy snapshot., An immutable, validated policy snapshot.

### Community 35 - "issue_credential"
Cohesion: 0.27
Nodes (15): _hash(), issue_credential(), Connection, Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)., Returns the credential in plaintext. The caller (the `hello` handler, or `pair…, Returns the device_id the credential belongs to, or None if it matches no live…, Returns the number of live credentials this call actually invalidated. Zero…, revoke_credential() (+7 more)

### Community 36 - "test_presence.py"
Cohesion: 0.18
Nodes (13): _echo_descriptor(), _FakeWS, parametrize, Presence (FR-16) — heartbeat-driven `last_seen_at` and 45s dead-peer detection.…, The dead-peer monitor drives an ordinary disconnect, not a revocation.…, test_dead_peer_after_45s_of_silence_closes_and_fails_in_flight(), test_dead_peer_timeout_leaves_disconnect_reason_at_default(), test_heartbeat_updates_last_seen_at() (+5 more)

### Community 37 - "AndroidNodeFixture"
Cohesion: 0.12
Nodes (14): test_hello_with_a_returning_credential_resolves_the_same_device_id(), _revoking_handler(), Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is…, _require_str_or_none(), Welcome, test_welcome_credential_defaults_to_none_and_round_trips_present_as_null(), AndroidNodeFixture, Connect and complete pairing or credential authentication. (+6 more)

### Community 38 - "mint_pairing_code"
Cohesion: 0.11
Nodes (39): burn_attempt(), code_is_live(), consume_pairing_code(), _hash_code(), mint_pairing_code(), NoPairingCodeAvailableError, Connection, RuntimeError (+31 more)

### Community 39 - "Capability Descriptors (name/version/input_schema/output_schema)"
Cohesion: 0.16
Nodes (14): device.status@1 capability, device.status@1 is deliberately not what device_status_get calls, diagnostics.echo@1 capability, notifications.send@1 capability, notifications.send@1 input schema byte-identical to schemas.py NOTIFICATIONS_SEND (minus device field), HDP-0 Amendments v0.2 (credential verification, welcome.credential, revoke sent), Capability Descriptors (name/version/input_schema/output_schema), HDP Envelope (hdp/type/id/ts/corr/payload) (+6 more)

### Community 40 - "daemon.py"
Cohesion: 0.12
Nodes (23): Event, AlreadyRunningError, _check_and_claim_pid(), _ensure_policy_file(), main(), _pid_is_live(), Path, RuntimeError (+15 more)

### Community 41 - "test_tools.py"
Cohesion: 0.23
Nodes (11): _assert_structured_failure(), _clean_runtime_singleton(), fixture, parametrize, FR-1: every handler returns parseable JSON and never propagates an exception,…, `device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable…, FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}`…, test_device_status_get_succeeds_with_zero_nodes() (+3 more)

### Community 42 - "_NodeSession"
Cohesion: 0.26
Nodes (5): ClientWebSocketResponse, _NodeSession, Any, Per-connection dispatch state: which invocation ids have been cancelled by the…, M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a…

### Community 43 - "asyncio"
Cohesion: 0.13
Nodes (9): asyncio, Fault injection for the conformance suite (m1-plan.md §7). Every fault is…, Protocol-level observability for frames received by the reference node., test_invoke_frame_is_logged_before_dispatch(), _WebSocket, The HDP/0 envelope: `{"hdp", "type", "id", "ts", "corr", "payload"}` — see…, HDP wire version and the known-message-type boundary. The full HDP/0 type set,…, LogCaptureFixture (+1 more)

### Community 44 - "runtime.py"
Cohesion: 0.11
Nodes (20): The plugin-side entry to daemon-owned invocation-time resolution., Hermes Device Plugin package. `register(ctx)` below, plus `cli.py` and…, get_runtime(), `HDPRuntime` — the pattern the whole architecture bets on (ADR-0002,…, The one `HDPRuntime` for this process, built at first use. Do not call this…, LLM-facing tool schemas — plain dicts, imported by nothing else in this…, lazy_singleton(), T (+12 more)

### Community 45 - "InvokeResult"
Cohesion: 0.29
Nodes (9): InvokeResult, The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is…, _FakeRuntime, _FakeTransport, _patched(), The plugin forwards unresolved invocations to the daemon-owned live resolver., Reintroducing plugin-side list/select logic or leaking `device` to the node…, test_invoke_forwards_unresolved_request_and_strips_routing_device() (+1 more)

### Community 46 - "_RecordingCtx"
Cohesion: 0.21
Nodes (7): `register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on…, Task 17 / FR-18: two more renderers of the same underlying operations,…, D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side…, _RecordingCtx, test_register_also_registers_the_hdp_cli_command_and_slash_command(), test_register_does_not_spawn_the_hdp_runtime_thread(), test_register_registers_exactly_three_async_device_tools()

### Community 47 - "test_node_cli.py"
Cohesion: 0.13
Nodes (17): build_parser(), _default_bridge_url(), main(), ArgumentParser, `hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect…, Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`., Python HDP reference node package., `python -m hdp_reference_node` entrypoint — equivalent to the `hdp-node`… (+9 more)

### Community 48 - "test_device_bound_pairing.py"
Cohesion: 0.19
Nodes (28): _connection(), _enroll(), _last(), _new_key(), parametrize, HDP-0.md Amendments (v0.4): challenge-response enrollment and device-bound…, A guesser who lands the right code but holds no matching key gets nothing, and…, Domain separation. Without distinct contexts a captured enrollment exchange… (+20 more)

### Community 49 - "M2 bridge extraction"
Cohesion: 0.22
Nodes (10): Directional dependencies, hdp-bridge, hdp_proto codec, hdp-spec, hermes-device-plugin, Unix-socket control plane, M0 plugin spike, M2 bridge extraction (+2 more)

### Community 50 - "BridgeTransport"
Cohesion: 0.20
Nodes (3): BridgeTransport, Protocol, The eight operations `engine.py` and the plugin's diagnostics/status surface…

### Community 51 - "Hello"
Cohesion: 0.20
Nodes (13): Hello, Node → Bridge, first frame on a new connection. `hello` doubles as the node's…, parametrize, A pre-v0.3 node omits the key entirely; that must stay a valid `hello`, not a…, Optional, not untyped — same posture as a non-string `credential`., Amendments v0.3. Emitting the key as an explicit null (rather than omitting it)…, test_from_wire_tolerates_unknown_fields(), test_hello_platform_defaults_to_none_and_round_trips_present_as_null() (+5 more)

### Community 53 - "Repository Guidelines"
Cohesion: 0.22
Nodes (9): Cross-package conformance tests, Graphify knowledge graph, hdp-reference-node, Hermes Device Protocol uv workspace, Repository Guidelines, make dev-install, M0-M4 milestone exit gates, Claude working instructions (+1 more)

### Community 54 - "001_initial.sql"
Cohesion: 0.28
Nodes (8): approvals, capabilities, credentials, devices, invocations, pairing_codes, policy_grants, schema_version

### Community 55 - "Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect)"
Cohesion: 0.22
Nodes (9): device_offline error code, invocation_timeout error code, late_result error code (log-only), malformed_result error code, schema_drift error code (log-only), HDP Error Taxonomy (closed enumeration of error codes), Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect), HDP Message Types (hello, welcome, capabilities, invoke, ack, cancel, result, progress, revoke, heartbeat, error) (+1 more)

### Community 56 - "acceptance job"
Cohesion: 0.29
Nodes (8): acceptance job, check job, make acceptance, make check, CI workflow, oracle-docs M0-M4 plan, HermesDeviceProtocol, M4 real-Hermes acceptance

### Community 57 - "Envelope"
Cohesion: 0.11
Nodes (19): BaseException, ControlServer, Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call…, Operator-only verb (`hermes hdp devices` at Task 17 was ultimately built…, Operator-only verb backing `hermes hdp audit` / `/hdp audit` — read-only, but…, Return daemon-memory approvals; none are durable while pending., Operator-only verb (FR-15, §4.4) — the CLI's `hdp-bridge devices revoke`…, Envelope (+11 more)

### Community 59 - "register_cli_command"
Cohesion: 0.29
Nodes (7): Any, Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement…, register_cli_command(), Any, Register the three device tools in toolset `device`, all `is_async=True`…, register(), test_register_cli_command_registers_hdp()

### Community 60 - "NodeConnection"
Cohesion: 0.12
Nodes (8): NodeConnection, Started alongside `run()`'s own read loop and reaped in that same `finally`, on…, Best-effort — HDP-0.md §7: the caller has already removed the pending-table…, M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing…, Every failed pairing handshake looks identical on the wire and charges the…, A failed proof on an enrollment burns budget like any other pairing failure; a…, Append now, drop anything outside the 60s window, and report whether the…, Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node…

### Community 61 - "hdp-proto"
Cohesion: 0.80
Nodes (5): hdp-bridge, hdp-proto, hdp-reference-node, hermes-device-plugin, hermes-device-protocol

### Community 62 - "bridge_stub"
Cohesion: 0.50
Nodes (4): AppRunner, bridge_stub(), fixture, _serve()

### Community 63 - "build_app"
Cohesion: 0.21
Nodes (12): Application, ConnectionFactory, _blobs_reserved(), build_app(), _health(), _make_socket_handler(), Any, Path (+4 more)

### Community 65 - "_backoff_delay"
Cohesion: 0.50
Nodes (4): _backoff_delay(), FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based. The 30s ceiling…, FR-14, which the previous `min(30.0, 0.5 * (2 ** (attempt - 1)))` met on none…, test_backoff_starts_at_one_second_is_capped_at_thirty_and_is_jittered()

### Community 68 - "Android Node Contract"
Cohesion: 0.25
Nodes (7): Android lifecycle and security guidance, Android Node Contract, M6 bridge handoff, Protocol conformance target, Scope and first capability profile, State model, Wire contract

### Community 70 - "_ImmediateConnection"
Cohesion: 0.25
Nodes (3): _ImmediateConnection, _StaticPolicy, test_sensitive_denial_audits_full_args_and_policy_snapshot_only_in_audit()

### Community 71 - "test_connection_auth.py"
Cohesion: 0.16
Nodes (14): _FakeWS, `_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired…, HDP-0.md Amendments v0.3. Without this the registry hardcodes "unknown" and…, Every pre-v0.3 node omits the field; it must keep pairing, not fail closed., Both handshake paths run through `_register_device`, so a node that starts…, _read_audit_records(), test_hello_with_a_previously_consumed_pairing_code_is_auth_failed(), test_hello_with_a_valid_pairing_code_pairs_and_returns_a_credential() (+6 more)

### Community 72 - "tests/conftest.py"
Cohesion: 0.50
Nodes (3): _hermes_home(), fixture, Test-wide fixtures for `hermes_device_plugin`. Real Hermes always sets…

### Community 73 - "test_scaffold.py"
Cohesion: 0.50
Nodes (3): Scaffold sanity tests., Keep `pytest` green before milestone implementation tests are added., test_scaffold_exists()

### Community 74 - "device_keys.py"
Cohesion: 0.18
Nodes (13): EllipticCurvePublicKey, InvalidDeviceKeyError, key_is_usable(), load_public_key(), new_nonce(), ValueError, Device public-key handling for HDP-0.md Amendments (v0.4). The bridge verifies…, The presented `device_pubkey` is not a usable EC P-256 public key. (+5 more)

### Community 75 - "test_revocation.py"
Cohesion: 0.21
Nodes (9): Connection, Operator-initiated revocation (FR-15, §4.4) — immediate and total, four steps…, Returns the number of live credentials actually invalidated — `0` for an…, revoke_device(), _FakeWS, Operator-initiated revocation (FR-15, §4.4) — the four-step order enforced in…, test_revoke_fails_in_flight_invocation_with_revoked_not_device_offline(), test_revoke_invalidates_credential_sends_revoke_frame_and_fails_in_flight() (+1 more)

### Community 77 - "_FakeWS"
Cohesion: 0.22
Nodes (3): _FakeWS, Challenge, Bridge → Node (Amendments v0.4). A fresh nonce the node must sign to prove it…

### Community 84 - "PolicyEngine"
Cohesion: 0.07
Nodes (27): Connection, Path, _NoDuplicateSafeLoader, PolicyEngine, PolicyValidationError, ValueError, Fail-closed HDP permission policy evaluation and reloads., Marker used to keep the PyYAML import out of module import paths. (+19 more)

## Knowledge Gaps
- **43 isolated node(s):** `schema_version`, `pairing_codes`, `policy_grants`, `approvals`, `invocations` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Envelope` connect `Envelope` to `SocketTransport`, `.new`, `Registry`, `._handle`, `control.py`, `hdp_bridge/__init__.py`, `InvokeRequest`, `InvocationsMem`, `test_m4_resolution.py`, `AuditWriter`, `_ResolvedTarget`, `test_server.py`, `node.py`, `test_presence.py`, `AndroidNodeFixture`, `_NodeSession`, `asyncio`, `test_device_bound_pairing.py`, `NodeConnection`, `_ImmediateConnection`, `test_connection_auth.py`, `_FakeWS`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `Registry` connect `Registry` to `.new`, `.__init__`, `control.py`, `hdp_bridge/__init__.py`, `InvocationsMem`, `test_m4_resolution.py`, `.known_active_device_ids`, `_ResolvedTarget`, `test_plugin_cli.py`, `test_server.py`, `_serve_claimed`, `issue_credential`, `test_presence.py`, `AndroidNodeFixture`, `daemon.py`, `test_device_bound_pairing.py`, `Envelope`, `NodeConnection`, `_ImmediateConnection`, `test_connection_auth.py`, `test_revocation.py`, `_FakeWS`, `PolicyEngine`, `.__init__`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `NodeConnection` connect `NodeConnection` to `test_faults.py`, `.new`, `Registry`, `server.py`, `.__init__`, `control.py`, `InvocationsMem`, `AuditWriter`, `_ResolvedTarget`, `test_server.py`, `_serve_claimed`, `CapabilityDescriptor`, `issue_credential`, `test_presence.py`, `AndroidNodeFixture`, `daemon.py`, `test_device_bound_pairing.py`, `Hello`, `Envelope`, `test_connection_auth.py`, `test_revocation.py`, `_FakeWS`, `PolicyEngine`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `Registry` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Registry` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `NodeConnection` (e.g. with `AuditWriter` and `InvocationsMem`) actually correct?**
  _`NodeConnection` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `InvocationsMem` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`InvocationsMem` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `Envelope` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Envelope` has 26 INFERRED edges - model-reasoned connections that need verification._