# Graph Report - .  (2026-08-19)

## Corpus Check
- 57 files · ~61,728 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1463 nodes · 3297 edges · 97 communities (71 shown, 26 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 261 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96

## God Nodes (most connected - your core abstractions)
1. `Registry` - 88 edges
2. `InvocationsMem` - 86 edges
3. `NodeConnection` - 67 edges
4. `ControlServer` - 62 edges
5. `SocketTransport` - 52 edges
6. `AuditWriter` - 45 edges
7. `ApprovalManager` - 39 edges
8. `connect()` - 29 edges
9. `_server()` - 27 edges
10. `PolicyEngine` - 26 edges

## Surprising Connections (you probably didn't know these)
- `_register_device()` --calls--> `DeviceRecord`  [INFERRED]
  hermes-device-plugin/tests/test_plugin_cli.py → hdp-bridge/hdp_bridge/types.py
- `_FakeWS` --uses--> `Welcome`  [INFERRED]
  hdp-bridge/tests/test_connection_auth.py → hdp-spec/hdp_proto/messages.py
- `_Harness` --uses--> `CapabilityDescriptor`  [INFERRED]
  hdp-bridge/tests/test_server.py → hdp-spec/hdp_proto/capabilities.py
- `_Harness` --uses--> `Envelope`  [INFERRED]
  hdp-bridge/tests/test_server.py → hdp-spec/hdp_proto/envelope.py
- `_Harness` --uses--> `Hello`  [INFERRED]
  hdp-bridge/tests/test_server.py → hdp-spec/hdp_proto/messages.py

## Import Cycles
- 3-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 4-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`
- 5-file cycle: `hermes-device-plugin/hermes_device_plugin/__init__.py -> hermes-device-plugin/hermes_device_plugin/tools.py -> hermes-device-plugin/hermes_device_plugin/engine.py -> hermes-device-plugin/hermes_device_plugin/runtime.py -> hermes-device-plugin/hermes_device_plugin/transport/socket.py -> hermes-device-plugin/hermes_device_plugin/__init__.py`

## Hyperedges (group relationships)
- **M2 Bridge Daemon Architecture** — readme_m2_bridge_extraction, agents_hdp_bridge, readme_sqlite_device_registry, readme_websocket_pairing, readme_control_plane [EXTRACTED 1.00]
- **HDP Closed Error-Code Taxonomy Members** — hdp_spec_errors_taxonomy, hdp_spec_errors_bridge_unavailable, hdp_spec_errors_not_implemented, hdp_spec_errors_no_matching_device, hdp_spec_errors_capability_unsupported, hdp_spec_errors_ambiguous_device, hdp_spec_errors_device_offline, hdp_spec_errors_invocation_timeout, hdp_spec_errors_malformed_result, hdp_spec_errors_version_incompatible, hdp_spec_errors_auth_failed, hdp_spec_errors_policy_denied, hdp_spec_errors_approval_denied, hdp_spec_errors_approval_timeout, hdp_spec_errors_revoked, hdp_spec_errors_late_result, hdp_spec_errors_schema_drift [EXTRACTED 0.95]
- **Three MVP HDP Capabilities Advertised by Reference Node** — hdp_spec_capabilities_device_status_1, hdp_spec_capabilities_diagnostics_echo_1, hdp_spec_capabilities_notifications_send_1, hdp_spec_hdp_0_capability_descriptors [EXTRACTED 0.95]
- **hermes-device Plugin Tools Provided by plugin.yaml** — hermes_device_plugin_hermes_device_plugin_plugin_yaml_manifest, hermes_device_plugin_tool_device_notifications_send, hermes_device_plugin_tool_device_status_get, hermes_device_plugin_tool_hdp_echo [EXTRACTED 0.95]

## Communities (97 total, 26 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (63): _NoDuplicateSafeLoader, PolicyEngine, PolicyTable, PolicyValidationError, Path, Fail-closed HDP permission policy evaluation and reloads., Resolve a device/capability pair using the documented four layers., Return this snapshot's configured target for one capability, if any. (+55 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (42): InvokeRequest, One unresolved capability invocation for daemon-side live resolution. Carries…, _bridge_unavailable(), Envelope, Future, PendingApproval, StreamReader, StreamWriter (+34 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (49): Hello, Process, ResultMsg, bridge(), bridge_log(), _bridge_proc(), bridge_url(), _hermes_home() (+41 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (52): read_frame(), write_frame(), control_request(), _error_detail(), Envelope, Operator-surface orchestration, owned by `hdp_bridge` and shared by both…, Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if…, Make one operator control-plane request without importing the plugin transport. (+44 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (36): CapabilityRecord, DeviceRecord, Path, SQLite-backed device registry (§3, §3.1). `online` state is never persisted —…, Return active device ids valid for policy references., No pairing exists yet (M2 pairing work) — a device enters this table only by…, Insert-or-replace the device row and fully replace its capability set (FR-8's…, Registry (+28 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (41): acceptance, CompletedProcess, Popen, skipif, _acceptance_environment(), _assert_plugin_and_tools(), _chat(), _device_tool_count() (+33 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (34): Application, ConnectionFactory, _blobs_reserved(), _bound_port(), build_app(), HdpServer, _health(), _make_socket_handler() (+26 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (24): ApprovalManager, ApprovalResolution, PendingApproval, Connection, In-memory approval lifecycle with terminal SQLite decision records., Return a stable presentation order without exposing internal state., Resolve one pending approval and persist exactly one terminal outcome., Terminally expire every approval whose 120-second deadline has elapsed. (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (20): _cancel_and_drain(), ControlServer, _invoke_failure(), Any, Envelope, Future, A failed `ctl_invoke_reply`, mirroring `embedded.py`'s `_failure` helper.…, Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call… (+12 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (28): _decode_crockford(), _encode_crockford(), InvalidULIDError, is_valid(), new(), parse(), ValueError, Hand-rolled ULID mint/parse — stdlib only, no `ulid` dependency (SDR-3). A ULID… (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (30): ApprovalScope, ApprovalState, StrEnum, Terminal approval outcomes persisted to the registry., The permitted scope choices for an approval decision., Raised when an approval is no longer pending., UnknownApprovalError, _approval_args_summary() (+22 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (31): _control_request(), main(), Envelope, Path, Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback…, _run_approval_resolve(), _run_approvals_list(), _run_audit_tail() (+23 more)

### Community 12 - "Community 12"
Cohesion: 0.10
Nodes (18): DeviceInfo, PendingApproval, An HDP `pending_approval` state (seed §17). Unreachable at M0 — the stub never…, InprocTransport, _LoopbackInvocations, _LoopbackRegistry, PendingApproval, The M0/M1 loopback `BridgeTransport`: no server, no socket, no node. This… (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (23): InvocationsMem, The bridge-side pending-invocation table — id → in-flight state. Backs real…, Atomically remove and return the entry (or `None` if already gone) without…, Tracks in-flight invocations. Empty by construction; entries live only between…, Called when an `ack` frame arrives. Returns `False` (a silent no-op) for an…, `InvocationsMem` in isolation — no server, no socket, no node., `fail_both=True` — the opt-in `revoke_device`'s explicit step 4 uses, so a…, Default `fail_both=False` behavior — only the not-yet-done ack future gets the… (+15 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (27): FaultConfig, Connect, advertise, dispatch forever, reconnecting with exponential backoff on…, run(), _abrupt_close_handler(), _auth_failed_handler(), _capture_explicit_credential_handler(), _pairing_handler(), parametrize (+19 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (23): BaseException, err(), Error, ErrorCode, ok(), Any, StrEnum, The closed HDP error-code taxonomy and the model-facing result envelope.… (+15 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (16): Per-connection lifecycle for one node's WebSocket. One `NodeConnection` per…, HDP bridge daemon package., _connect_and_hello(), Direct wire-level tests for `hdp_bridge.server` — a fake "node" is a raw…, test_hello_welcome_handshake_registers_the_device(), test_malformed_frame_gets_an_error_reply_and_stays_open(), EnvelopeError, ValueError (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.16
Nodes (7): NodeConnection, Envelope, Started alongside `run()`'s own read loop and reaped in that same `finally`, on…, Best-effort — HDP-0.md §7: the caller has already removed the pending-table…, M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing…, Append now, drop anything outside the 60s window, and report whether the…, Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node…

### Community 18 - "Community 18"
Cohesion: 0.17
Nodes (17): _FakeWS, `_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired…, _read_audit_records(), test_hello_with_a_previously_consumed_pairing_code_is_auth_failed(), test_hello_with_a_returning_credential_resolves_the_same_device_id(), test_hello_with_a_revoked_credential_is_auth_failed(), test_hello_with_a_valid_pairing_code_pairs_and_returns_a_credential(), test_hello_with_an_invalid_pairing_code_is_auth_failed() (+9 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (22): handle_hdp_command(), Any, Hermes `/hdp status|devices|audit` slash command — the **read-only** half of…, `args` is accepted as either a raw string (split on whitespace here) or an…, Registers `/hdp` (design §2's confinement rule — this module is one of the…, register_command(), _hermes_home(), fixture (+14 more)

### Community 20 - "Community 20"
Cohesion: 0.14
Nodes (18): _apply_pragmas(), connect(), _migrate(), Connection, Path, RuntimeError, SQLite connection factory and forward-only migration runner (§3.1, §3.2)., The database's `schema_version` is higher than this build of `hdp_bridge` knows… (+10 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (19): Any, ValueError, Capability descriptors and output-schema validation. `CapabilityDescriptor` is…, Raised by `validate_output` when `data` does not match `output_schema`. The…, Never `cls(**d)` — read fields by name, tolerate unknown fields, matching the…, Validate `data` against `descriptor.output_schema`. Raises…, SchemaValidationError, _validate() (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (20): Publish one complete live bridge sample (also the focused-test seam)., _update_availability(), echo_available(), notifications_available(), Visibility hint for ``notifications.send``; never an invocation gate. Hermes…, Visibility hint for ``diagnostics.echo``; never an invocation gate. Hermes may…, BridgeStatus, CapabilityInfo (+12 more)

### Community 23 - "Community 23"
Cohesion: 0.15
Nodes (19): Event, AlreadyRunningError, _check_and_claim_pid(), main(), _pid_is_live(), `hdp-bridge serve` — the foreground daemon entrypoint (§5.5). PID-file…, Another live hdp-bridge process already holds this profile's PID file., Treat `pid_path` as a *claim* to verify, not a fact to trust. If it names a… (+11 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (19): _build_parser(), main(), ArgumentParser, `hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-…, Calls `ctl_audit_tail` over the control socket rather than reading…, The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here,…, CLI-only (finding I1) — `/hdp pair --new` no longer reaches this; see…, render_approvals() (+11 more)

### Community 25 - "Community 25"
Cohesion: 0.16
Nodes (20): invoke(), Any, Forward one unresolved request and return the daemon's model-facing result., get_runtime(), The one `HDPRuntime` for this process, built at first use. Do not call this…, _echo(), _handler(), _notifications_send() (+12 more)

### Community 26 - "Community 26"
Cohesion: 0.16
Nodes (19): registry_db_path(), CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see…, render_devices(), render_devices_revoke(), bridge_daemon(), fixture, `hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`,…, No daemon reachable — `render_devices_revoke` falls back to the direct DB-only… (+11 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (18): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), Path (+10 more)

### Community 28 - "Community 28"
Cohesion: 0.16
Nodes (13): AuditWriter, Path, Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON…, Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb —…, parametrize, Exercises O_APPEND directly: two separate `record()` calls (two separate…, `os.fsync` is actually invoked for events in the security-relevant subset, not…, test_no_plaintext_credential_ever_reaches_the_audit_file() (+5 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (16): The node-side second enforcement point (docs/design.md §4). Trivial at M1:…, AuthFailed, _backoff_delay(), _connect_and_serve(), Exception, Path, The reference node: connects to an HDP bridge over WebSocket, advertises its…, FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based. The 30s ceiling… (+8 more)

### Community 30 - "Community 30"
Cohesion: 0.21
Nodes (16): bridge_addr_path(), control_socket_path(), hdp_home(), hermes_home(), pid_path(), policy_path(), Path, Profile-scoped paths, timeouts, and defaults for the standalone `hdp-bridge`… (+8 more)

### Community 31 - "Community 31"
Cohesion: 0.14
Nodes (11): CapabilityDescriptor, One entry in a `capabilities` message's full-replacement list (HDP-0.md §2, §6)., CancelMsg, ErrorMsg, Heartbeat, ProgressMsg, Typed payload dataclasses for each HDP/0 message type (hdp-spec/HDP-0.md §2).…, Bridge → Node, sent best-effort on timeout or explicit cancellation. (+3 more)

### Community 32 - "Community 32"
Cohesion: 0.15
Nodes (10): asyncio, The plugin-side entry to daemon-owned invocation-time resolution., Hermes Device Plugin package. `register(ctx)` below, plus `cli.py` and…, `HDPRuntime` — the pattern the whole architecture bets on (ADR-0002,…, LLM-facing tool schemas — plain dicts, imported by nothing else in this…, lazy_singleton(), T, Stdlib fallback for `plugins.plugin_utils.lazy_singleton`, used only when no… (+2 more)

### Community 33 - "Community 33"
Cohesion: 0.15
Nodes (10): AbstractEventLoop, HDPRuntime, Any, Future, T, `await self.transport.start()` runs to completion before anything checks…, Publish one bounded live sample, retaining the last hint when sampling fails. A…, Schedule `coro` onto the HDP loop from any thread. Returns a plain… (+2 more)

### Community 34 - "Community 34"
Cohesion: 0.18
Nodes (11): _correlate(), _log_task_exception(), StreamReader, StreamWriter, Stamp `reply.corr` with the request envelope's `id`. Applied to *every* reply,…, `add_done_callback` hook for every fire-and-forget task this module spawns.…, Two independent mechanisms — not a poll loop guessing how many event-loop ticks…, Read loop for one control connection. `ctl_invoke` is dispatched *off* this… (+3 more)

### Community 35 - "Community 35"
Cohesion: 0.29
Nodes (14): _hash(), issue_credential(), Connection, Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)., Returns the credential in plaintext. The caller (the `hello` handler, or `pair…, Returns the device_id the credential belongs to, or None if it matches no live…, Returns the number of live credentials this call actually invalidated. Zero…, revoke_credential() (+6 more)

### Community 36 - "Community 36"
Cohesion: 0.18
Nodes (12): _echo_descriptor(), _FakeWS, CapabilityDescriptor, parametrize, Presence (FR-16) — heartbeat-driven `last_seen_at` and 45s dead-peer detection.…, The dead-peer monitor drives an ordinary disconnect, not a revocation.…, test_dead_peer_after_45s_of_silence_closes_and_fails_in_flight(), test_dead_peer_timeout_leaves_disconnect_reason_at_default() (+4 more)

### Community 37 - "Community 37"
Cohesion: 0.27
Nodes (13): consume_pairing_code(), _hash_code(), mint_pairing_code(), Connection, _random_code(), Pairing-code minting and atomic consumption (FR-11, §4.1). Minting is operator-…, The single atomic statement FR-11 requires — see docs/m2-plan.md §4.1 for why a…, FR-11's core claim: two nodes racing one code, exactly one gets a device_id. (+5 more)

### Community 38 - "Community 38"
Cohesion: 0.21
Nodes (9): Connection, Operator-initiated revocation (FR-15, §4.4) — immediate and total, four steps…, Returns the number of live credentials actually invalidated — `0` for an…, revoke_device(), _FakeWS, Operator-initiated revocation (FR-15, §4.4) — the four-step order enforced in…, test_revoke_fails_in_flight_invocation_with_revoked_not_device_offline(), test_revoke_invalidates_credential_sends_revoke_frame_and_fails_in_flight() (+1 more)

### Community 39 - "Community 39"
Cohesion: 0.16
Nodes (14): device.status@1 capability, device.status@1 is deliberately not what device_status_get calls, diagnostics.echo@1 capability, notifications.send@1 capability, notifications.send@1 input schema byte-identical to schemas.py NOTIFICATIONS_SEND (minus device field), HDP-0 Amendments v0.2 (credential verification, welcome.credential, revoke sent), Capability Descriptors (name/version/input_schema/output_schema), HDP Envelope (hdp/type/id/ts/corr/payload) (+6 more)

### Community 40 - "Community 40"
Cohesion: 0.30
Nodes (6): _capabilities_from_wire(), Any, _require_dict(), _require_int(), _require_str(), _require_str_or_none()

### Community 41 - "Community 41"
Cohesion: 0.21
Nodes (13): _assert_structured_failure(), _clean_runtime_singleton(), fixture, parametrize, FR-1: every handler returns parseable JSON and never propagates an exception,…, `device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable…, FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}`…, test_device_status_get_retains_device_and_capability_details() (+5 more)

### Community 42 - "Community 42"
Cohesion: 0.27
Nodes (6): ClientWebSocketResponse, _NodeSession, Any, Envelope, Per-connection dispatch state: which invocation ids have been cancelled by the…, M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a…

### Community 43 - "Community 43"
Cohesion: 0.17
Nodes (7): FaultConfig, Fault injection for the conformance suite (m1-plan.md §7). Every fault is…, Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`., Protocol-level observability for frames received by the reference node., test_invoke_frame_is_logged_before_dispatch(), _WebSocket, LogCaptureFixture

### Community 44 - "Community 44"
Cohesion: 0.19
Nodes (10): InvokeMsg, Bridge → Node. `corr` (on the envelope, not here) carries the bridge-minted…, Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is…, Welcome, parametrize, test_from_wire_tolerates_unknown_fields(), test_hello_rejects_malformed_hdp_versions(), test_invoke_msg_rejects_missing_deadline() (+2 more)

### Community 45 - "Community 45"
Cohesion: 0.29
Nodes (9): InvokeResult, The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is…, _FakeRuntime, _FakeTransport, _patched(), The plugin forwards unresolved invocations to the daemon-owned live resolver., Reintroducing plugin-side list/select logic or leaking `device` to the node…, test_invoke_forwards_unresolved_request_and_strips_routing_device() (+1 more)

### Community 46 - "Community 46"
Cohesion: 0.21
Nodes (7): `register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on…, Task 17 / FR-18: two more renderers of the same underlying operations,…, D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side…, _RecordingCtx, test_register_also_registers_the_hdp_cli_command_and_slash_command(), test_register_does_not_spawn_the_hdp_runtime_thread(), test_register_registers_exactly_three_async_device_tools()

### Community 47 - "Community 47"
Cohesion: 0.24
Nodes (8): build_parser(), _default_bridge_url(), main(), ArgumentParser, `hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect…, Python HDP reference node package., `python -m hdp_reference_node` entrypoint — equivalent to the `hdp-node`…, test_pair_code_and_explicit_credential_are_mutually_exclusive()

### Community 48 - "Community 48"
Cohesion: 0.18
Nodes (8): capability_available(), _CapabilityAvailability, Lock-protected capability snapshot read synchronously by Hermes ``check_fn``…, Return the latest visibility hint without creating or contacting the runtime., _reset_availability_for_tests(), _clean_runtime_singleton(), fixture, Every test starts and ends with no HDP thread alive, so leak assertions are…

### Community 49 - "Community 49"
Cohesion: 0.22
Nodes (10): Directional dependencies, hdp-bridge, hdp_proto codec, hdp-spec, hermes-device-plugin, Unix-socket control plane, M0 plugin spike, M2 bridge extraction (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.22
Nodes (10): hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), The host the aiohttp node-facing server binds to. Read fresh on every call…, The port the aiohttp node-facing server binds to. `0` (test convention)…, NFR-4's guard: binding to a non-loopback host is refused unless this is set., _ensure_policy_file(), Path (+2 more)

### Community 51 - "Community 51"
Cohesion: 0.27
Nodes (9): descriptors_for_overrides(), CapabilityDescriptor, Build the advertised descriptor set for repeatable ``NAME@N`` CLI overrides.…, parametrize, M4 reference-node CLI overrides used by the multi-node lifecycle harness., test_capability_version_overrides_reject_invalid_values(), test_capability_version_overrides_replace_only_named_capability_versions(), test_overridden_version_keeps_the_builtin_handler() (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.20
Nodes (3): BridgeTransport, Protocol, The eight operations `engine.py` and the plugin's diagnostics/status surface…

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (9): Cross-package conformance tests, Graphify knowledge graph, hdp-reference-node, Hermes Device Protocol uv workspace, Repository Guidelines, make dev-install, M0-M4 milestone exit gates, Claude working instructions (+1 more)

### Community 54 - "Community 54"
Cohesion: 0.28
Nodes (8): approvals, capabilities, credentials, devices, invocations, pairing_codes, policy_grants, schema_version

### Community 55 - "Community 55"
Cohesion: 0.22
Nodes (9): device_offline error code, invocation_timeout error code, late_result error code (log-only), malformed_result error code, schema_drift error code (log-only), HDP Error Taxonomy (closed enumeration of error codes), Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect), HDP Message Types (hello, welcome, capabilities, invoke, ack, cancel, result, progress, revoke, heartbeat, error) (+1 more)

### Community 56 - "Community 56"
Cohesion: 0.29
Nodes (8): acceptance job, check job, make acceptance, make check, CI workflow, oracle-docs M0-M4 plan, HermesDeviceProtocol, M4 real-Hermes acceptance

### Community 57 - "Community 57"
Cohesion: 0.25
Nodes (4): Fail every pending invocation regardless of device — used on transport shutdown…, A device's connection dropped (or was revoked): fail every invocation still…, Fail only calls dispatched through one concrete connection generation., Remove and fail every pending entry (all of them when `device_id` is `None`).…

### Community 58 - "Community 58"
Cohesion: 0.29
Nodes (4): CapabilitiesMsg, Either direction's `capabilities` frame: a full-set replacement, never a delta…, Bridge → Node. Declared per HDP-0.md §3.3; unused until M2's credential-…, RevokeMsg

### Community 59 - "Community 59"
Cohesion: 0.29
Nodes (7): Any, Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement…, register_cli_command(), Any, Register the three device tools in toolset `device`, all `is_async=True`…, register(), test_register_cli_command_registers_hdp()

### Community 60 - "Community 60"
Cohesion: 0.40
Nodes (3): Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like…, ResultMsg, test_result_msg_rejects_non_bool_ok()

### Community 61 - "Community 61"
Cohesion: 0.80
Nodes (5): hdp-bridge, hdp-proto, hdp-reference-node, hermes-device-plugin, hermes-device-protocol

### Community 62 - "Community 62"
Cohesion: 0.50
Nodes (4): AppRunner, bridge_stub(), fixture, _serve()

### Community 63 - "Community 63"
Cohesion: 0.50
Nodes (3): CapabilityDescriptor, Connection, WebSocketResponse

### Community 64 - "Community 64"
Cohesion: 0.50
Nodes (3): CapabilityDescriptor, Connection, Path

### Community 67 - "Community 67"
Cohesion: 0.50
Nodes (3): handle(), Any, `device.status@1` (hdp-spec/capabilities/device.status@1.md). Deliberately…

### Community 68 - "Community 68"
Cohesion: 0.50
Nodes (3): handle(), Any, `diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure…

### Community 69 - "Community 69"
Cohesion: 0.50
Nodes (3): handle(), Any, `notifications.send@1` (hdp-spec/capabilities/notifications.send@1.md). Prints…

### Community 71 - "Community 71"
Cohesion: 0.50
Nodes (4): render_status(), test_render_status_reports_healthy_against_a_real_daemon(), test_render_status_reports_unreachable_with_no_daemon(), test_hdp_status_delegates_to_render_status()

### Community 72 - "Community 72"
Cohesion: 0.50
Nodes (3): _hermes_home(), fixture, Test-wide fixtures for `hermes_device_plugin`. Real Hermes always sets…

### Community 73 - "Community 73"
Cohesion: 0.50
Nodes (3): Scaffold sanity tests., Keep `pytest` green before milestone implementation tests are added., test_scaffold_exists()

## Knowledge Gaps
- **37 isolated node(s):** `schema_version`, `pairing_codes`, `policy_grants`, `approvals`, `invocations` (+32 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ControlServer` connect `Community 8` to `Community 64`, `Community 0`, `Community 34`, `Community 3`, `Community 4`, `Community 65`, `Community 7`, `Community 10`, `Community 13`, `Community 15`, `Community 17`, `Community 50`, `Community 23`, `Community 28`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `InvocationsMem` connect `Community 13` to `Community 0`, `Community 3`, `Community 4`, `Community 8`, `Community 10`, `Community 16`, `Community 17`, `Community 18`, `Community 23`, `Community 36`, `Community 38`, `Community 50`, `Community 57`, `Community 63`, `Community 64`, `Community 65`, `Community 66`, `Community 74`, `Community 75`, `Community 76`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `SocketTransport` connect `Community 1` to `Community 32`, `Community 2`, `Community 71`, `Community 12`, `Community 45`, `Community 15`, `Community 22`, `Community 24`, `Community 26`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `Registry` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Registry` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `InvocationsMem` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`InvocationsMem` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `NodeConnection` (e.g. with `AuditWriter` and `InvocationsMem`) actually correct?**
  _`NodeConnection` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `ControlServer` (e.g. with `ApprovalManager` and `ApprovalScope`) actually correct?**
  _`ControlServer` has 21 INFERRED edges - model-reasoned connections that need verification._