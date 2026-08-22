# Graph Report - hermes-device-protocol  (2026-08-21)

## Corpus Check
- 115 files · ~62,858 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1465 nodes · 3679 edges · 87 communities (71 shown, 16 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 317 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9183738d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- InvokeRequest
- SocketTransport
- base.py
- .new
- Registry
- test_seed_success_criterion.py
- HdpServer
- ApprovalManager
- Envelope
- ids.py
- CapabilityDescriptor
- test_cli.py
- DeviceInfo
- InvocationsMem
- test_node_auth.py
- err
- test_server.py
- ._reject_malformed
- Hello
- test_plugin_commands.py
- connect
- validate_output
- BridgeStatus
- _ResolvedTarget
- hermes_device_plugin/cli.py
- tools.py
- test_plugin_cli.py
- hermes_device_plugin/config.py
- AuditWriter
- node.py
- hdp_bridge/config.py
- Any
- test_repeated_runtime_start_stop_does_not_leak_fds_or_threads
- HDPRuntime
- PolicyTable
- issue_credential
- NodeConnection
- AndroidNodeFixture
- test_errors_conformance.py
- Capability Descriptors (name/version/input_schema/output_schema)
- test_daemon.py
- test_tools.py
- _NodeSession
- test_node_invocation_logging.py
- test_runtime.py
- InvokeResult
- _RecordingCtx
- test_node_cli.py
- runtime.py
- M2 bridge extraction
- _serve_claimed
- test_messages.py
- socket.py
- Repository Guidelines
- 001_initial.sql
- Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect)
- acceptance job
- CancelMsg
- _insert_device_with_credential
- register_cli_command
- Welcome
- hdp-proto
- bridge_stub
- _FakeControlServer
- diagnostics.py
- _backoff_delay
- render_pair_new
- device_status.py
- notifications.py
- tests/conftest.py
- test_scaffold.py
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

## God Nodes (most connected - your core abstractions)
1. `Registry` - 90 edges
2. `InvocationsMem` - 87 edges
3. `NodeConnection` - 80 edges
4. `Envelope` - 71 edges
5. `ControlServer` - 66 edges
6. `SocketTransport` - 54 edges
7. `connect()` - 53 edges
8. `CapabilityDescriptor` - 51 edges
9. `DeviceRecord` - 47 edges
10. `AuditWriter` - 45 edges

## Surprising Connections (you probably didn't know these)
- `_register_device()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_devices_revoke_against_a_real_daemon_reaches_the_control_socket()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_devices_revoke_of_an_unknown_device_reports_no_such_device()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_devices_revoke_offline_fallback_records_via_marker()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py
- `test_render_pair_new_mints_a_code_and_records_no_plaintext_audit_entry()` --calls--> `registry_db_path()`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/config.py

## Import Cycles
- 3-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 4-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 5-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`

## Hyperedges (group relationships)
- **M2 Bridge Daemon Architecture** — readme_m2_bridge_extraction, agents_hdp_bridge, readme_sqlite_device_registry, readme_websocket_pairing, readme_control_plane [EXTRACTED 1.00]
- **HDP Closed Error-Code Taxonomy Members** — hdp_spec_errors_taxonomy, hdp_spec_errors_bridge_unavailable, hdp_spec_errors_not_implemented, hdp_spec_errors_no_matching_device, hdp_spec_errors_capability_unsupported, hdp_spec_errors_ambiguous_device, hdp_spec_errors_device_offline, hdp_spec_errors_invocation_timeout, hdp_spec_errors_malformed_result, hdp_spec_errors_version_incompatible, hdp_spec_errors_auth_failed, hdp_spec_errors_policy_denied, hdp_spec_errors_approval_denied, hdp_spec_errors_approval_timeout, hdp_spec_errors_revoked, hdp_spec_errors_late_result, hdp_spec_errors_schema_drift [EXTRACTED 0.95]
- **Three MVP HDP Capabilities Advertised by Reference Node** — hdp_spec_capabilities_device_status_1, hdp_spec_capabilities_diagnostics_echo_1, hdp_spec_capabilities_notifications_send_1, hdp_spec_hdp_0_capability_descriptors [EXTRACTED 0.95]
- **hermes-device Plugin Tools Provided by plugin.yaml** — hermes_device_plugin_hermes_device_plugin_plugin_yaml_manifest, hermes_device_plugin_tool_device_notifications_send, hermes_device_plugin_tool_device_status_get, hermes_device_plugin_tool_hdp_echo [EXTRACTED 0.95]

## Communities (87 total, 16 thin omitted)

### Community 0 - "InvokeRequest"
Cohesion: 0.19
Nodes (20): InvokeRequest, One unresolved capability invocation for daemon-side live resolution. Carries…, bridge_daemon(), fake_control_server(), _invoke_request(), fixture, `SocketTransport` — the plugin-side client of `hdp_bridge/control.py`'s Unix-…, `start()`'s eager connect must not be fatal — the first real call after the… (+12 more)

### Community 1 - "SocketTransport"
Cohesion: 0.13
Nodes (12): PendingApproval, Attempt to (re)connect. Must be called with `self._lock` held. Returns `True`…, Send one request and await its reply, holding no lock while waiting. The lock…, Operator-only verb, deliberately **not** on `BridgeTransport` — never reachable…, Implements `BridgeTransport` (verified structurally by the tests, not by…, Eagerly opens the connection once, matching…, SocketTransport, test_cancelled_invoke_does_not_hang_when_cancel_reply_never_arrives() (+4 more)

### Community 2 - "base.py"
Cohesion: 0.08
Nodes (56): Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like…, ResultMsg, `BridgeTransport` — the ADR-0004 extraction seam. `engine.py` depends on this…, Process, bridge(), bridge_log(), _bridge_proc(), bridge_url() (+48 more)

### Community 3 - ".new"
Cohesion: 0.07
Nodes (72): read_frame(), write_frame(), control_request(), Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if…, Make one operator control-plane request without importing the plugin transport., _revoke_via_control_socket(), _connect_and_hello(), ctl_conn() (+64 more)

### Community 4 - "Registry"
Cohesion: 0.06
Nodes (69): Validate decoded policy data and construct one immutable snapshot., Path, SQLite-backed device registry (§3, §3.1). `online` state is never persisted —…, Return active device ids valid for policy references., No pairing exists yet (M2 pairing work) — a device enters this table only by…, Insert-or-replace the device row and fully replace its capability set (FR-8's…, Registry, CapabilityRecord (+61 more)

### Community 5 - "test_seed_success_criterion.py"
Cohesion: 0.14
Nodes (34): acceptance, CompletedProcess, Popen, _acceptance_environment(), _assert_plugin_and_tools(), _chat(), _device_tool_count(), _hermes_command() (+26 more)

### Community 6 - "HdpServer"
Cohesion: 0.08
Nodes (31): Application, ConnectionFactory, _blobs_reserved(), _bound_port(), build_app(), HdpServer, _health(), _make_socket_handler() (+23 more)

### Community 7 - "ApprovalManager"
Cohesion: 0.09
Nodes (19): ApprovalManager, ApprovalResolution, PendingApproval, Connection, In-memory approval lifecycle with terminal SQLite decision records., Return a stable presentation order without exposing internal state., Resolve one pending approval and persist exactly one terminal outcome., Terminally expire every approval whose 120-second deadline has elapsed. (+11 more)

### Community 8 - "Envelope"
Cohesion: 0.09
Nodes (21): ControlServer, _correlate(), _log_task_exception(), StreamReader, StreamWriter, Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call…, Operator-only verb (`hermes hdp devices` at Task 17 was ultimately built…, Operator-only verb backing `hermes hdp audit` / `/hdp audit` — read-only, but… (+13 more)

### Community 9 - "ids.py"
Cohesion: 0.17
Nodes (18): _decode_crockford(), _encode_crockford(), InvalidULIDError, is_valid(), new(), parse(), ValueError, Hand-rolled ULID mint/parse — stdlib only, no `ulid` dependency (SDR-3). A ULID… (+10 more)

### Community 10 - "CapabilityDescriptor"
Cohesion: 0.09
Nodes (30): ApprovalScope, ApprovalState, StrEnum, Terminal approval outcomes persisted to the registry., The permitted scope choices for an approval decision., _approval_args_summary(), _InvokeReq, _malformed_invoke() (+22 more)

### Community 11 - "test_cli.py"
Cohesion: 0.13
Nodes (24): _control_request(), main(), Path, Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback…, _run_approval_resolve(), _run_approvals_list(), _run_audit_tail(), _run_devices_revoke() (+16 more)

### Community 12 - "DeviceInfo"
Cohesion: 0.10
Nodes (18): DeviceInfo, PendingApproval, An HDP `pending_approval` state (seed §17). Unreachable at M0 — the stub never…, InprocTransport, _LoopbackInvocations, _LoopbackRegistry, PendingApproval, The M0/M1 loopback `BridgeTransport`: no server, no socket, no node. This… (+10 more)

### Community 13 - "InvocationsMem"
Cohesion: 0.07
Nodes (31): DeviceDisconnected, InvocationsMem, Any, Exception, Called when a `result` frame arrives. Returns `False` for an unknown id — the…, Atomically remove and return the entry (or `None` if already gone) without…, Fail every pending invocation regardless of device — used on transport shutdown…, A device's connection dropped (or was revoked): fail every invocation still… (+23 more)

### Community 14 - "test_node_auth.py"
Cohesion: 0.16
Nodes (23): FaultConfig, Connect, advertise, dispatch forever, reconnecting with exponential backoff on…, run(), _abrupt_close_handler(), _auth_failed_handler(), parametrize, The reference node's M2 auth behaviour (final-review findings I7 and I8).…, D6: a second node's runtime-only credential must leave the stored default… (+15 more)

### Community 15 - "err"
Cohesion: 0.22
Nodes (10): BaseException, err(), ErrorCode, StrEnum, Build the failure half of the model-facing result envelope. `detail` becomes…, Stable declaration order — this is the order the M1 conformance test diffs…, test_err_accepts_an_exception_as_detail(), test_err_carries_structured_context_without_overwriting_core_fields() (+2 more)

### Community 16 - "test_server.py"
Cohesion: 0.18
Nodes (5): client(), _Harness, fixture, Direct wire-level tests for `hdp_bridge.server` — a fake "node" is a raw…, The same shared-state wiring `EmbeddedTransport` used to own at M1: one…

### Community 17 - "._reject_malformed"
Cohesion: 0.18
Nodes (4): Append now, drop anything outside the 60s window, and report whether the…, ErrorMsg, Either direction. Same shape `hdp_proto.errors.err()` produces for the model-…, test_result_msg_rejects_non_bool_ok()

### Community 18 - "Hello"
Cohesion: 0.20
Nodes (13): _FakeWS, `_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired…, _read_audit_records(), test_hello_with_a_previously_consumed_pairing_code_is_auth_failed(), test_hello_with_a_returning_credential_resolves_the_same_device_id(), test_hello_with_a_revoked_credential_is_auth_failed(), test_hello_with_a_valid_pairing_code_pairs_and_returns_a_credential(), test_hello_with_an_invalid_pairing_code_is_auth_failed() (+5 more)

### Community 19 - "test_plugin_commands.py"
Cohesion: 0.12
Nodes (22): handle_hdp_command(), Any, Hermes `/hdp status|devices|audit` slash command — the **read-only** half of…, `args` is accepted as either a raw string (split on whitespace here) or an…, Registers `/hdp` (design §2's confinement rule — this module is one of the…, register_command(), _hermes_home(), fixture (+14 more)

### Community 20 - "connect"
Cohesion: 0.07
Nodes (44): _error_detail(), pair_new(), Operator-surface orchestration, owned by `hdp_bridge` and shared by both…, Mint a pairing code and return it in plaintext. There is no control-plane verb…, Revoke `device_id`, returning the line the caller should render. Prefers the…, revoke(), consume_pairing_code(), _hash_code() (+36 more)

### Community 21 - "validate_output"
Cohesion: 0.16
Nodes (16): Any, ValueError, Never `cls(**d)` — read fields by name, tolerate unknown fields, matching the…, Validate `data` against `descriptor.output_schema`. Raises…, _validate(), validate_output(), parametrize, diagnostics.echo@1's `payload` field has no nested schema — any JSON value… (+8 more)

### Community 22 - "BridgeStatus"
Cohesion: 0.19
Nodes (16): Publish one complete live bridge sample (also the focused-test seam)., _update_availability(), echo_available(), notifications_available(), Visibility hint for ``notifications.send``; never an invocation gate. Hermes…, Visibility hint for ``diagnostics.echo``; never an invocation gate. Hermes may…, BridgeStatus, CapabilityInfo (+8 more)

### Community 23 - "_ResolvedTarget"
Cohesion: 0.16
Nodes (13): _cancel_and_drain(), _invoke_failure(), Any, Future, A failed `ctl_invoke_reply`, mirroring `embedded.py`'s `_failure` helper.…, Cancel unfinished lifecycle futures and consume every terminal exception., Resolve live state, authorize one snapshot, dispatch, then validate., One invocation's live selection and immutable dispatch descriptor. (+5 more)

### Community 24 - "hermes_device_plugin/cli.py"
Cohesion: 0.18
Nodes (16): `hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-…, Calls `ctl_audit_tail` over the control socket rather than reading…, render_approvals(), render_audit(), render_policy(), render_status(), resolve_approval(), _run() (+8 more)

### Community 25 - "tools.py"
Cohesion: 0.10
Nodes (25): Error, ok(), Any, The closed HDP error-code taxonomy and the model-facing result envelope.…, The `error` half of the model-facing result envelope., Build the success half of the model-facing result envelope: `{"ok": true,…, test_ok_shape(), invoke() (+17 more)

### Community 26 - "test_plugin_cli.py"
Cohesion: 0.16
Nodes (17): CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see…, render_devices(), render_devices_revoke(), bridge_daemon(), fixture, `hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`,…, No daemon reachable — `render_devices_revoke` falls back to the direct DB-only…, Finding I4, offline-fallback half: no live credential means nothing was… (+9 more)

### Community 27 - "hermes_device_plugin/config.py"
Cohesion: 0.14
Nodes (18): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), Path (+10 more)

### Community 28 - "AuditWriter"
Cohesion: 0.07
Nodes (29): asyncio, AuditWriter, Path, Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON…, Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb —…, Per-connection lifecycle for one node's WebSocket. One `NodeConnection` per…, AlreadyRunningError, RuntimeError (+21 more)

### Community 29 - "node.py"
Cohesion: 0.18
Nodes (12): The node-side second enforcement point (docs/design.md §4). Trivial at M1:…, AuthFailed, _connect_and_serve(), Exception, Path, The reference node: connects to an HDP bridge over WebSocket, advertises its…, The bridge rejected this node's credential. Deliberately **not** an `OSError`…, Write the bridge-issued credential 0600, with no world-readable window at any… (+4 more)

### Community 30 - "hdp_bridge/config.py"
Cohesion: 0.20
Nodes (17): bridge_addr_path(), control_socket_path(), hdp_home(), hermes_home(), pid_path(), policy_path(), Path, Profile-scoped paths, timeouts, and defaults for the standalone `hdp-bridge`… (+9 more)

### Community 31 - "Any"
Cohesion: 0.14
Nodes (12): _capabilities_from_wire(), ProgressMsg, Any, Node → Bridge. Declared per HDP-0.md §2; no M1 producer or consumer., Bridge → Node. Declared per HDP-0.md §3.3; unused until M2's credential-…, _require_dict(), _require_int(), _require_str() (+4 more)

### Community 32 - "test_repeated_runtime_start_stop_does_not_leak_fds_or_threads"
Cohesion: 0.33
Nodes (8): skipif, _fd_count(), _hdp_thread_count(), timeout, M1-1's risk mitigation (m1-plan.md §9): the embedded aiohttp server's…, `HDPRuntime.close()` already blocks on `Thread.join()`, but the loop thread…, test_repeated_runtime_start_stop_does_not_leak_fds_or_threads(), _wait_for_no_hdp_threads()

### Community 33 - "HDPRuntime"
Cohesion: 0.14
Nodes (10): AbstractEventLoop, HDPRuntime, Any, Future, T, `await self.transport.start()` runs to completion before anything checks…, Publish one bounded live sample, retaining the last hint when sampling fails. A…, Schedule `coro` onto the HDP loop from any thread. Returns a plain… (+2 more)

### Community 34 - "PolicyTable"
Cohesion: 0.12
Nodes (9): PolicyTable, Path, Resolve a device/capability pair using the documented four layers., Return this snapshot's configured target for one capability, if any., Capture the current immutable policy snapshot., An immutable, validated policy snapshot., _ImmediateConnection, _StaticPolicy (+1 more)

### Community 35 - "issue_credential"
Cohesion: 0.16
Nodes (21): _hash(), issue_credential(), Connection, Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)., Returns the credential in plaintext. The caller (the `hello` handler, or `pair…, Returns the device_id the credential belongs to, or None if it matches no live…, Returns the number of live credentials this call actually invalidated. Zero…, revoke_credential() (+13 more)

### Community 36 - "NodeConnection"
Cohesion: 0.11
Nodes (19): _InvokeRequestLike, NodeConnection, Connection, Protocol, WebSocketResponse, Started alongside `run()`'s own read loop and reaped in that same `finally`, on…, Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node…, _FakeWS (+11 more)

### Community 37 - "AndroidNodeFixture"
Cohesion: 0.22
Nodes (8): CapabilitiesMsg, Either direction's `capabilities` frame: a full-set replacement, never a delta…, AndroidNodeFixture, Reconnect with the stored credential and preserve the bridge-issued identity., Send a complete capability replacement, matching FR-8., Close the current connection and reap its reader task., A small HDP peer with Android M5 policy semantics. The fixture stores the…, Connect and complete pairing or credential authentication.

### Community 38 - "test_errors_conformance.py"
Cohesion: 0.43
Nodes (6): _parse_errors_md(), FR-32: `hdp-spec/errors.md` (the normative doc) must be identical to…, Catches the inverse drift: a code declared in errors.md but removed from…, test_errors_md_code_set_and_order_match_error_code(), test_errors_md_has_no_orphaned_entries(), test_errors_md_hints_match_hints_dict()

### Community 39 - "Capability Descriptors (name/version/input_schema/output_schema)"
Cohesion: 0.16
Nodes (14): device.status@1 capability, device.status@1 is deliberately not what device_status_get calls, diagnostics.echo@1 capability, notifications.send@1 capability, notifications.send@1 input schema byte-identical to schemas.py NOTIFICATIONS_SEND (minus device field), HDP-0 Amendments v0.2 (credential verification, welcome.credential, revoke sent), Capability Descriptors (name/version/input_schema/output_schema), HDP Envelope (hdp/type/id/ts/corr/payload) (+6 more)

### Community 40 - "test_daemon.py"
Cohesion: 0.19
Nodes (14): _check_and_claim_pid(), _pid_is_live(), Treat `pid_path` as a *claim* to verify, not a fact to trust. If it names a…, serve(), A partial-bind failure (`hdp_server.start()` succeeds, `control.start()`…, The PID claim happens before *any* binding. A failure anywhere between the…, A `bridge.pid` file that isn't a parseable integer (corrupted, truncated, ...)…, _read_audit_records() (+6 more)

### Community 41 - "test_tools.py"
Cohesion: 0.23
Nodes (11): _assert_structured_failure(), _clean_runtime_singleton(), fixture, parametrize, FR-1: every handler returns parseable JSON and never propagates an exception,…, `device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable…, FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}`…, test_device_status_get_succeeds_with_zero_nodes() (+3 more)

### Community 42 - "_NodeSession"
Cohesion: 0.26
Nodes (5): ClientWebSocketResponse, _NodeSession, Any, Per-connection dispatch state: which invocation ids have been cancelled by the…, M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a…

### Community 43 - "test_node_invocation_logging.py"
Cohesion: 0.22
Nodes (5): Fault injection for the conformance suite (m1-plan.md §7). Every fault is…, Protocol-level observability for frames received by the reference node., test_invoke_frame_is_logged_before_dispatch(), _WebSocket, LogCaptureFixture

### Community 44 - "test_runtime.py"
Cohesion: 0.22
Nodes (12): get_runtime(), The one `HDPRuntime` for this process, built at first use. Do not call this…, _clean_runtime_singleton(), fixture, The real M0 deliverable (docs/m0-plan.md §6.5): `HDPRuntime` called from all…, Every test starts and ends with no HDP thread alive, so leak assertions are…, The race `lazy_singleton` exists for: N threads calling `get_runtime()` cold,…, Unknown startup state is visible and a synchronous check never builds the… (+4 more)

### Community 45 - "InvokeResult"
Cohesion: 0.29
Nodes (9): InvokeResult, The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is…, _FakeRuntime, _FakeTransport, _patched(), The plugin forwards unresolved invocations to the daemon-owned live resolver., Reintroducing plugin-side list/select logic or leaking `device` to the node…, test_invoke_forwards_unresolved_request_and_strips_routing_device() (+1 more)

### Community 46 - "_RecordingCtx"
Cohesion: 0.21
Nodes (7): `register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on…, Task 17 / FR-18: two more renderers of the same underlying operations,…, D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side…, _RecordingCtx, test_register_also_registers_the_hdp_cli_command_and_slash_command(), test_register_does_not_spawn_the_hdp_runtime_thread(), test_register_registers_exactly_three_async_device_tools()

### Community 47 - "test_node_cli.py"
Cohesion: 0.13
Nodes (17): build_parser(), _default_bridge_url(), main(), ArgumentParser, `hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect…, Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`., Python HDP reference node package., `python -m hdp_reference_node` entrypoint — equivalent to the `hdp-node`… (+9 more)

### Community 48 - "runtime.py"
Cohesion: 0.09
Nodes (12): capability_available(), _CapabilityAvailability, `HDPRuntime` — the pattern the whole architecture bets on (ADR-0002,…, Lock-protected capability snapshot read synchronously by Hermes ``check_fn``…, Return the latest visibility hint without creating or contacting the runtime., _reset_availability_for_tests(), lazy_singleton(), T (+4 more)

### Community 49 - "M2 bridge extraction"
Cohesion: 0.22
Nodes (10): Directional dependencies, hdp-bridge, hdp_proto codec, hdp-spec, hermes-device-plugin, Unix-socket control plane, M0 plugin spike, M2 bridge extraction (+2 more)

### Community 50 - "_serve_claimed"
Cohesion: 0.18
Nodes (12): Event, hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), The host the aiohttp node-facing server binds to. Read fresh on every call…, The port the aiohttp node-facing server binds to. `0` (test convention)…, NFR-4's guard: binding to a non-loopback host is refused unless this is set., _ensure_policy_file() (+4 more)

### Community 51 - "test_messages.py"
Cohesion: 0.18
Nodes (7): Ack, Heartbeat, Either direction's `ack` frame. Empty payload — the envelope's `corr` carries…, Either direction. Application-level heartbeat, belt-and-suspenders on top of…, parametrize, test_from_wire_tolerates_unknown_fields(), test_round_trip()

### Community 52 - "socket.py"
Cohesion: 0.24
Nodes (8): _bridge_unavailable(), Future, StreamReader, StreamWriter, M2 Unix-socket bridge transport — the client half of `hdp_bridge/control.py`'s…, Demultiplex every reply on one connection into the future that is waiting for…, _read_frame(), _write_frame()

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

### Community 57 - "CancelMsg"
Cohesion: 0.33
Nodes (3): Best-effort — HDP-0.md §7: the caller has already removed the pending-table…, CancelMsg, Bridge → Node, sent best-effort on timeout or explicit cancellation.

### Community 58 - "_insert_device_with_credential"
Cohesion: 0.33
Nodes (6): _insert_device_with_credential(), Task 17's gap-fix for the review finding carried forward from Task 16: with no…, A minimal `devices` row plus one live `credentials` row — the smallest state in…, Already-revoked is the same zero-rows case as never-existed — both are "nothing…, test_devices_revoke_offline_fallback_records_a_revoked_audit_entry(), test_devices_revoke_twice_reports_no_such_device_the_second_time()

### Community 59 - "register_cli_command"
Cohesion: 0.17
Nodes (12): _build_parser(), main(), Any, ArgumentParser, The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here,…, Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement…, register_cli_command(), Any (+4 more)

### Community 60 - "Welcome"
Cohesion: 0.19
Nodes (7): M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing…, _pairing_handler(), Completes a first-time pairing and issues a credential, then holds the socket…, _revoking_handler(), Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is…, Welcome, test_welcome_credential_defaults_to_none_and_round_trips_present_as_null()

### Community 61 - "hdp-proto"
Cohesion: 0.80
Nodes (5): hdp-bridge, hdp-proto, hdp-reference-node, hermes-device-plugin, hermes-device-protocol

### Community 62 - "bridge_stub"
Cohesion: 0.50
Nodes (4): AppRunner, bridge_stub(), fixture, _serve()

### Community 64 - "diagnostics.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure…

### Community 65 - "_backoff_delay"
Cohesion: 0.50
Nodes (4): _backoff_delay(), FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based. The 30s ceiling…, FR-14, which the previous `min(30.0, 0.5 * (2 ** (attempt - 1)))` met on none…, test_backoff_starts_at_one_second_is_capped_at_thirty_and_is_jittered()

### Community 66 - "render_pair_new"
Cohesion: 0.67
Nodes (3): CLI-only (finding I1) — `/hdp pair --new` no longer reaches this; see…, render_pair_new(), test_render_pair_new_mints_a_code_and_records_no_plaintext_audit_entry()

### Community 67 - "device_status.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `device.status@1` (hdp-spec/capabilities/device.status@1.md). Deliberately…

### Community 69 - "notifications.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `notifications.send@1` (hdp-spec/capabilities/notifications.send@1.md). Prints…

### Community 72 - "tests/conftest.py"
Cohesion: 0.50
Nodes (3): _hermes_home(), fixture, Test-wide fixtures for `hermes_device_plugin`. Real Hermes always sets…

### Community 73 - "test_scaffold.py"
Cohesion: 0.50
Nodes (3): Scaffold sanity tests., Keep `pytest` green before milestone implementation tests are added., test_scaffold_exists()

### Community 84 - "PolicyEngine"
Cohesion: 0.08
Nodes (27): Mode, _NoDuplicateSafeLoader, PolicyEngine, PolicyValidationError, StrEnum, ValueError, Fail-closed HDP permission policy evaluation and reloads., Marker used to keep the PyYAML import out of module import paths. (+19 more)

## Knowledge Gaps
- **37 isolated node(s):** `schema_version`, `pairing_codes`, `policy_grants`, `approvals`, `invocations` (+32 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Envelope` connect `Envelope` to `SocketTransport`, `.new`, `Registry`, `CapabilityDescriptor`, `test_cli.py`, `DeviceInfo`, `err`, `test_server.py`, `._reject_malformed`, `Hello`, `connect`, `_ResolvedTarget`, `AuditWriter`, `node.py`, `PolicyTable`, `NodeConnection`, `AndroidNodeFixture`, `_NodeSession`, `test_node_invocation_logging.py`, `socket.py`, `Welcome`, `_FakeControlServer`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `NodeConnection` connect `NodeConnection` to `base.py`, `issue_credential`, `Registry`, `AndroidNodeFixture`, `HdpServer`, `.new`, `Envelope`, `CapabilityDescriptor`, `InvocationsMem`, `Welcome`, `test_server.py`, `._reject_malformed`, `Hello`, `_serve_claimed`, `_ResolvedTarget`, `CancelMsg`, `AuditWriter`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `ControlServer` connect `Envelope` to `PolicyTable`, `.new`, `NodeConnection`, `Registry`, `ApprovalManager`, `test_daemon.py`, `CapabilityDescriptor`, `InvocationsMem`, `err`, `_serve_claimed`, `PolicyEngine`, `_ResolvedTarget`, `AuditWriter`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Registry` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Registry` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `InvocationsMem` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`InvocationsMem` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `NodeConnection` (e.g. with `AuditWriter` and `InvocationsMem`) actually correct?**
  _`NodeConnection` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `Envelope` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Envelope` has 24 INFERRED edges - model-reasoned connections that need verification._