# Graph Report - hermes-device-protocol  (2026-08-28)

## Corpus Check
- 135 files · ~77,156 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1901 nodes · 4910 edges · 107 communities (85 shown, 22 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 433 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b0a42682`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PolicyEngine
- SocketTransport
- start_node
- test_control.py
- Registry
- test_seed_success_criterion.py
- AndroidNodeFixture
- test_usb_bootstrap.py
- ControlServer
- ._handle
- PolicyTable
- test_cli.py
- InprocTransport
- InvocationsMem
- test_node_auth.py
- harness.py
- ApprovalManager
- Hello
- ids.py
- test_plugin_commands.py
- usb_accessory.py
- CapabilityDescriptor
- envelope.py
- test_lifecycle.py
- hermes_device_plugin/cli.py
- asyncio
- test_plugin_cli.py
- hermes_device_plugin/config.py
- control.py
- node.py
- _serve_claimed
- Any
- test_repeated_runtime_start_stop_does_not_leak_fds_or_threads
- HDPRuntime
- issue_credential
- test_node_invocation_logging.py
- test_external_node.py
- bridge_stub
- connect
- Capability Descriptors (name/version/input_schema/output_schema)
- test_server.py
- hdp_reference_node/cli.py
- tui.py
- device_keys.py
- test_tools.py
- InvokeResult
- _RecordingCtx
- BridgeTransport
- test_device_bound_pairing.py
- M2 bridge extraction
- EnrollmentCoordinator
- .from_wire
- AuditWriter
- Repository Guidelines
- 001_initial.sql
- Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect)
- acceptance job
- _FakeWS
- usb_bootstrap.py
- db.py
- NodeConnection
- hdp-proto
- ._read_loop
- daemon.py
- HDPApp
- Envelope
- test_errors_conformance.py
- Android Node Contract
- _InvokeRequestLike
- DeviceRoleManager
- _FakeControlServer
- tests/conftest.py
- test_scaffold.py
- test_android_node.py
- SentinelApprovalRequest
- Policy
- operations.py
- local_policy.py
- capabilities/__init__.py
- Malformed and Out-of-Sequence Frame Handling
- transport/__init__.py
- device_status.py
- diagnostics.py
- notifications.py
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
- register_cli_command
- AuthFailed
- render_audit
- .on_data_table_row_selected
- test_messages.py
- test_ctl_list_approvals_returns_an_empty_pending_set
- .new
- CancelMsg
- _write_frame

## God Nodes (most connected - your core abstractions)
1. `Registry` - 111 edges
2. `NodeConnection` - 103 edges
3. `InvocationsMem` - 95 edges
4. `connect()` - 93 edges
5. `Envelope` - 80 edges
6. `ControlServer` - 67 edges
7. `CapabilityDescriptor` - 58 edges
8. `Hello` - 57 edges
9. `EnrollmentCoordinator` - 55 edges
10. `SocketTransport` - 54 edges

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

## Communities (107 total, 22 thin omitted)

### Community 0 - "PolicyEngine"
Cohesion: 0.07
Nodes (27): _NoDuplicateSafeLoader, PolicyEngine, PolicyValidationError, Path, ValueError, Fail-closed HDP permission policy evaluation and reloads., Marker used to keep the PyYAML import out of module import paths., Own the current immutable policy snapshot and safely replace it after… (+19 more)

### Community 1 - "SocketTransport"
Cohesion: 0.09
Nodes (32): InvokeRequest, One unresolved capability invocation for daemon-side live resolution. Carries…, PendingApproval, Attempt to (re)connect. Must be called with `self._lock` held. Returns `True`…, Send one request and await its reply, holding no lock while waiting. The lock…, Operator-only verb, deliberately **not** on `BridgeTransport` — never reachable…, Implements `BridgeTransport` (verified structurally by the tests, not by…, Eagerly opens the connection once, matching… (+24 more)

### Community 2 - "start_node"
Cohesion: 0.20
Nodes (22): Process, Launch the real `hdp-node` CLI as a subprocess with the given `--fault` flags,…, Poll `bridge.list_devices()` until at least one device is online, or raise on…, Poll the `bridge_log` list (conftest.py's live-updated capture of the `hdp…, start_node(), stop_node(), wait_for_device(), wait_for_log() (+14 more)

### Community 3 - "test_control.py"
Cohesion: 0.17
Nodes (24): _connect_and_hello(), ctl_conn(), _ctl_invoke(), _ctl_invoke_envelope(), node_client(), fixture, `hdp_bridge.control` — the plugin↔bridge Unix-socket control plane.…, Finding I3, server half: `_handle` used to `await self._dispatch(...)` inline… (+16 more)

### Community 4 - "Registry"
Cohesion: 0.05
Nodes (82): _PendingHandshake, Per-connection lifecycle for one node's WebSocket. One `NodeConnection` per…, A challenge awaiting its proof (HDP-0.md Amendments v0.4). `pair_code` is set…, Validate decoded policy data and construct one immutable snapshot., Path, SQLite-backed device registry (§3, §3.1). `online` state is never persisted —…, Return active device ids valid for policy references., No pairing exists yet (M2 pairing work) — a device enters this table only by… (+74 more)

### Community 5 - "test_seed_success_criterion.py"
Cohesion: 0.14
Nodes (34): acceptance, CompletedProcess, Popen, _acceptance_environment(), _assert_plugin_and_tools(), _chat(), _device_tool_count(), _hermes_command() (+26 more)

### Community 6 - "AndroidNodeFixture"
Cohesion: 0.11
Nodes (16): _pairing_handler(), Completes a first-time pairing and issues a credential, then holds the socket…, _revoking_handler(), CapabilitiesMsg, Bridge → Node, reply to a successful `hello`. `credential` (M2, §4.3) is…, Either direction's `capabilities` frame: a full-set replacement, never a delta…, Welcome, test_welcome_credential_defaults_to_none_and_round_trips_present_as_null() (+8 more)

### Community 7 - "test_usb_bootstrap.py"
Cohesion: 0.13
Nodes (23): HostIdentityStore, _load_private_key(), EllipticCurvePrivateKey, EllipticCurvePublicKey, Path, Persistent signing identity for one Hermes/HDP host., A host's P-256 key, its wire-format public key, and stable fingerprint., _write_private_key() (+15 more)

### Community 8 - "ControlServer"
Cohesion: 0.10
Nodes (22): BaseException, ControlServer, Best-effort cancel, mirroring `EmbeddedTransport.cancel` — safe to call…, Operator-only verb (FR-15, §4.4) — the CLI's `hdp devices revoke` reaches this…, Isolates the exact race `ControlServer.close()`'s backlog-drain step exists…, test_close_drains_a_connection_still_in_the_kernel_accept_backlog(), err(), Error (+14 more)

### Community 9 - "._handle"
Cohesion: 0.17
Nodes (11): _correlate(), _log_task_exception(), StreamReader, StreamWriter, Stamp `reply.corr` with the request envelope's `id`. Applied to *every* reply,…, `add_done_callback` hook for every fire-and-forget task this module spawns.…, Two independent mechanisms — not a poll loop guessing how many event-loop ticks…, Read loop for one control connection. `ctl_invoke` is dispatched *off* this… (+3 more)

### Community 10 - "PolicyTable"
Cohesion: 0.18
Nodes (6): PolicyTable, Resolve a device/capability pair using the documented four layers., Return this snapshot's configured target for one capability, if any., An immutable, validated policy snapshot., _Harness, One `Registry`/`InvocationsMem`/`connections`/`descriptors` set, shared between…

### Community 11 - "test_cli.py"
Cohesion: 0.10
Nodes (36): _control_request(), main(), Path, Thin renderer over `operations.revoke` — the daemon-reachable/offline-fallback…, _run_approval_resolve(), _run_approvals_list(), _run_audit_tail(), _run_devices_list() (+28 more)

### Community 12 - "InprocTransport"
Cohesion: 0.11
Nodes (10): InprocTransport, PendingApproval, Implements `BridgeTransport` (verified structurally by the tests, not by…, Real at M0: this is what `HDPRuntime` calls on its owned loop, and the shape…, The M0 loopback stub in isolation — no server, no socket, no node (design §6.4)., test_device_info_carries_fr13_fields_with_safe_defaults(), test_invoke_round_trips_through_the_real_codec_and_succeeds(), test_list_devices_is_empty_at_m0() (+2 more)

### Community 13 - "InvocationsMem"
Cohesion: 0.07
Nodes (31): DeviceDisconnected, InvocationsMem, Any, Exception, The bridge-side pending-invocation table — id → in-flight state. Backs real…, Called when a `result` frame arrives. Returns `False` for an unknown id — the…, Fail every pending invocation regardless of device — used on transport shutdown…, A device's connection dropped (or was revoked): fail every invocation still… (+23 more)

### Community 14 - "test_node_auth.py"
Cohesion: 0.16
Nodes (20): FaultConfig, ClientWebSocketResponse, Connect, advertise, dispatch forever, reconnecting with exponential backoff on…, run(), _abrupt_close_handler(), _auth_failed_handler(), parametrize, The reference node's M2 auth behaviour (final-review findings I7 and I8).… (+12 more)

### Community 15 - "harness.py"
Cohesion: 0.14
Nodes (21): bridge(), bridge_log(), _bridge_proc(), bridge_url(), external_node_mode(), _hermes_home(), _managed_bridge_proc(), fixture (+13 more)

### Community 16 - "ApprovalManager"
Cohesion: 0.08
Nodes (23): ApprovalManager, ApprovalResolution, ApprovalScope, PendingApproval, Connection, In-memory approval lifecycle with terminal SQLite decision records., Return a stable presentation order without exposing internal state., Resolve one pending approval and persist exactly one terminal outcome. (+15 more)

### Community 17 - "Hello"
Cohesion: 0.17
Nodes (18): _FakeWS, `_handle_hello`'s M2 auth branch (§3, §4.3, §4.4): M2 does not accept unpaired…, HDP-0.md Amendments v0.3. Without this the registry hardcodes "unknown" and…, Every pre-v0.3 node omits the field; it must keep pairing, not fail closed., Both handshake paths run through `_register_device`, so a node that starts…, _read_audit_records(), test_hello_with_a_previously_consumed_pairing_code_is_auth_failed(), test_hello_with_a_returning_credential_resolves_the_same_device_id() (+10 more)

### Community 18 - "ids.py"
Cohesion: 0.17
Nodes (18): _decode_crockford(), _encode_crockford(), InvalidULIDError, is_valid(), new(), parse(), ValueError, Hand-rolled ULID mint/parse — stdlib only, no `ulid` dependency (SDR-3). A ULID… (+10 more)

### Community 19 - "test_plugin_commands.py"
Cohesion: 0.12
Nodes (23): handle_hdp_command(), Any, Hermes `/hdp status|devices|audit` slash command — the **read-only** half of…, `args` is accepted as either a raw string (split on whitespace here) or an…, Registers `/hdp` (design §2's confinement rule — this module is one of the…, register_command(), _hermes_home(), fixture (+15 more)

### Community 20 - "usb_accessory.py"
Cohesion: 0.12
Nodes (19): BinaryIO, _find_android(), _LibusbStream, _payload(), Exception, Path, RuntimeError, Host adapter for the Android USB-accessory bootstrap line protocol. (+11 more)

### Community 21 - "CapabilityDescriptor"
Cohesion: 0.11
Nodes (25): Connection, WebSocketResponse, Resolve one target synchronously so registry and connection state cannot…, _ResolutionFailure, CapabilityDescriptor, Any, ValueError, Capability descriptors and output-schema validation. `CapabilityDescriptor` is… (+17 more)

### Community 22 - "envelope.py"
Cohesion: 0.10
Nodes (33): The HDP/0 envelope: `{"hdp", "type", "id", "ts", "corr", "payload"}` — see…, Stdlib-only HDP protocol codec package., Publish one complete live bridge sample (also the focused-test seam)., _update_availability(), echo_available(), notifications_available(), Visibility hint for ``notifications.send``; never an invocation gate. Hermes…, Visibility hint for ``diagnostics.echo``; never an invocation gate. Hermes may… (+25 more)

### Community 23 - "test_lifecycle.py"
Cohesion: 0.25
Nodes (19): Node → Bridge. `ok=True` carries `data`; `ok=False` carries `error` shaped like…, ResultMsg, _authenticate_raw_node(), _echo_request(), _enroll_raw_node(), _new_device_key(), ClientWebSocketResponse, EllipticCurvePrivateKey (+11 more)

### Community 24 - "hermes_device_plugin/cli.py"
Cohesion: 0.12
Nodes (22): main(), _build_parser(), main(), ArgumentParser, `hermes hdp {status,devices,pair,audit}` — the CLI-native renderer of `hdp-…, The `hermes hdp ...` operator entry point. `asyncio.run()` only appears here,…, Explain the physical bootstrap requirement without creating a remote pairing…, render_approvals() (+14 more)

### Community 25 - "asyncio"
Cohesion: 0.08
Nodes (34): asyncio, invoke(), Any, The plugin-side entry to daemon-owned invocation-time resolution., Forward one unresolved request and return the daemon's model-facing result., capability_available(), _CapabilityAvailability, get_runtime() (+26 more)

### Community 26 - "test_plugin_cli.py"
Cohesion: 0.17
Nodes (18): registry_db_path(), CLI-only (finding I1) — `/hdp devices revoke` no longer reaches this; see…, render_devices(), render_devices_revoke(), bridge_daemon(), fixture, `hermes hdp {status,devices,pair,audit}` (Task 17). Named `test_plugin_cli.py`,…, Finding I4, offline-fallback half: no live credential means nothing was… (+10 more)

### Community 27 - "hermes_device_plugin/config.py"
Cohesion: 0.14
Nodes (18): bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home(), hermes_home(), Path (+10 more)

### Community 28 - "control.py"
Cohesion: 0.08
Nodes (36): ApprovalState, StrEnum, Terminal approval outcomes persisted to the registry., _approval_args_summary(), _cancel_and_drain(), _invoke_failure(), _InvokeReq, _malformed_invoke() (+28 more)

### Community 29 - "node.py"
Cohesion: 0.15
Nodes (18): _backoff_delay(), _connect_and_serve(), _load_or_create_key(), _public_key_b64(), EllipticCurvePrivateKey, Path, The reference node: connects to an HDP bridge over WebSocket, advertises its…, FR-14: exponential 1s -> 30s, jittered. `attempt` is 1-based. The 30s ceiling… (+10 more)

### Community 30 - "_serve_claimed"
Cohesion: 0.06
Nodes (53): Event, advertised_wss_endpoint(), bridge_addr_path(), control_socket_path(), hdp_allow_remote(), hdp_bind_host(), hdp_bind_port(), hdp_home() (+45 more)

### Community 31 - "Any"
Cohesion: 0.09
Nodes (18): Ack, _capabilities_from_wire(), ErrorMsg, Heartbeat, ProgressMsg, Any, Typed payload dataclasses for each HDP/0 message type (hdp-spec/HDP-0.md §2).…, Either direction's `ack` frame. Empty payload — the envelope's `corr` carries… (+10 more)

### Community 32 - "test_repeated_runtime_start_stop_does_not_leak_fds_or_threads"
Cohesion: 0.33
Nodes (8): skipif, _fd_count(), _hdp_thread_count(), timeout, M1-1's risk mitigation (m1-plan.md §9): the embedded aiohttp server's…, `HDPRuntime.close()` already blocks on `Thread.join()`, but the loop thread…, test_repeated_runtime_start_stop_does_not_leak_fds_or_threads(), _wait_for_no_hdp_threads()

### Community 33 - "HDPRuntime"
Cohesion: 0.14
Nodes (10): AbstractEventLoop, HDPRuntime, Any, Future, T, `await self.transport.start()` runs to completion before anything checks…, Publish one bounded live sample, retaining the last hint when sampling fails. A…, Schedule `coro` onto the HDP loop from any thread. Returns a plain… (+2 more)

### Community 34 - "issue_credential"
Cohesion: 0.29
Nodes (14): _hash(), issue_credential(), Connection, Device credential issuance, verification, and revocation (FR-12, §4.3, §4.4)., Returns the credential in plaintext. The caller (the `hello` handler, or `pair…, Returns the device_id the credential belongs to, or None if it matches no live…, Returns the number of live credentials this call actually invalidated. Zero…, revoke_credential() (+6 more)

### Community 35 - "test_node_invocation_logging.py"
Cohesion: 0.22
Nodes (5): Fault injection for the conformance suite (m1-plan.md §7). Every fault is…, Protocol-level observability for frames received by the reference node., test_invoke_frame_is_logged_before_dispatch(), _WebSocket, LogCaptureFixture

### Community 36 - "test_external_node.py"
Cohesion: 0.21
Nodes (13): _await_paired_node(), M6: the conformance rows run against a real, externally-connected node. Opt-in…, M6 exit gate 4's node-local layer. `diagnostics.echo@1` is deliberately outside…, M6 exit gate 3. Driven by the operator: background/kill the app, then bring it…, Return the connected node, pairing one first if none is present. Checks before…, M6 exit gate 1 and 2., M6 exit gate 4's success path, plus the schema conformance FR-6 asks for: the…, test_external_node_denies_a_capability_it_does_not_advertise() (+5 more)

### Community 37 - "bridge_stub"
Cohesion: 0.50
Nodes (4): AppRunner, bridge_stub(), fixture, _serve()

### Community 38 - "connect"
Cohesion: 0.10
Nodes (50): burn_attempt(), code_is_live(), consume_pairing_code(), _hash_code(), mint_pairing_code(), NoPairingCodeAvailableError, pairing_status(), PairingStatus (+42 more)

### Community 39 - "Capability Descriptors (name/version/input_schema/output_schema)"
Cohesion: 0.16
Nodes (14): device.status@1 capability, device.status@1 is deliberately not what device_status_get calls, diagnostics.echo@1 capability, notifications.send@1 capability, notifications.send@1 input schema byte-identical to schemas.py NOTIFICATIONS_SEND (minus device field), HDP-0 Amendments v0.2 (credential verification, welcome.credential, revoke sent), Capability Descriptors (name/version/input_schema/output_schema), HDP Envelope (hdp/type/id/ts/corr/payload) (+6 more)

### Community 40 - "test_server.py"
Cohesion: 0.06
Nodes (41): Application, ConnectionFactory, _blobs_reserved(), _bound_port(), build_app(), HdpServer, _health(), _make_socket_handler() (+33 more)

### Community 41 - "hdp_reference_node/cli.py"
Cohesion: 0.19
Nodes (9): build_parser(), _default_bridge_url(), main(), ArgumentParser, `hdp-node` — the reference node's CLI (m1-plan.md §8 step 1: `hdp-node connect…, Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`., Python HDP reference node package., `python -m hdp_reference_node` entrypoint — equivalent to the `hdp-node`… (+1 more)

### Community 42 - "tui.py"
Cohesion: 0.11
Nodes (12): ComposeResult, Approvals, Audit, Base, Devices, Menu, Pair, Textual operator dashboard; it renders existing HDP operations, not a new… (+4 more)

### Community 43 - "device_keys.py"
Cohesion: 0.16
Nodes (15): InvalidDeviceKeyError, key_is_usable(), load_public_key(), new_nonce(), EllipticCurvePublicKey, ValueError, Device public-key handling for HDP-0.md Amendments (v0.4). The bridge verifies…, Verify a base64 ECDSA-SHA256 signature over canonical protocol bytes. (+7 more)

### Community 44 - "test_tools.py"
Cohesion: 0.23
Nodes (11): _assert_structured_failure(), _clean_runtime_singleton(), fixture, parametrize, FR-1: every handler returns parseable JSON and never propagates an exception,…, `device_status_get` bypasses `engine.invoke` (FR-2) — its deepest reachable…, FR-2 / M0 exit gate step 6: exactly `{"ok": true, "data": {"devices": []}}`…, test_device_status_get_succeeds_with_zero_nodes() (+3 more)

### Community 45 - "InvokeResult"
Cohesion: 0.29
Nodes (9): InvokeResult, The transport's answer to an `InvokeRequest`. Exactly one of `data`/`error` is…, _FakeRuntime, _FakeTransport, _patched(), The plugin forwards unresolved invocations to the daemon-owned live resolver., Reintroducing plugin-side list/select logic or leaking `device` to the node…, test_invoke_forwards_unresolved_request_and_strips_routing_device() (+1 more)

### Community 46 - "_RecordingCtx"
Cohesion: 0.21
Nodes (7): `register(ctx)` — FR-1's "exactly three tools" and FR-2's "no check_fn on…, Task 17 / FR-18: two more renderers of the same underlying operations,…, D6 / ADR-0006: registration is metadata only. Building HDPRuntime as a side…, _RecordingCtx, test_register_also_registers_the_hdp_cli_command_and_slash_command(), test_register_does_not_spawn_the_hdp_runtime_thread(), test_register_registers_exactly_three_async_device_tools()

### Community 47 - "BridgeTransport"
Cohesion: 0.18
Nodes (3): BridgeTransport, Protocol, The eight operations `engine.py` and the plugin's diagnostics/status surface…

### Community 48 - "test_device_bound_pairing.py"
Cohesion: 0.17
Nodes (34): fingerprint(), Return the SHA-256 fingerprint of a validated P-256 public key's canonical DER…, _connection(), _enroll(), _last(), _new_key(), parametrize, HDP-0.md Amendments (v0.4): challenge-response enrollment and device-bound… (+26 more)

### Community 49 - "M2 bridge extraction"
Cohesion: 0.22
Nodes (10): Directional dependencies, hdp-bridge, hdp_proto codec, hdp-spec, hermes-device-plugin, Unix-socket control plane, M0 plugin spike, M2 bridge extraction (+2 more)

### Community 50 - "EnrollmentCoordinator"
Cohesion: 0.09
Nodes (30): EnrollmentAlreadyPendingError, EnrollmentCoordinator, EnrollmentError, EnrollmentLockedError, EnrollmentNotFoundError, EnrollmentNotReadyError, _identifier_hash(), _now_ms() (+22 more)

### Community 51 - ".from_wire"
Cohesion: 0.16
Nodes (20): _capture_explicit_credential_handler(), Capture the hello so the explicit, non-persistent credential contract is…, The frame's `hdp` field names a version we do not speak. Per HDP-0.md §3, this…, The frame's `type` field is missing or not in `KNOWN_TYPES`. Per HDP-0.md §5,…, Validate and construct. Never `cls(**d)` — an unknown top-level key must not…, UnknownTypeError, UnsupportedVersionError, HDP wire version and the known-message-type boundary. The full HDP/0 type set,… (+12 more)

### Community 52 - "AuditWriter"
Cohesion: 0.10
Nodes (22): AuditWriter, Path, Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON…, Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb —…, Connection, Operator-initiated revocation (FR-15, §4.4) — immediate and total, four steps…, Returns the number of live credentials actually invalidated — `0` for an…, revoke_device() (+14 more)

### Community 53 - "Repository Guidelines"
Cohesion: 0.22
Nodes (9): Cross-package conformance tests, Graphify knowledge graph, hdp-reference-node, Hermes Device Protocol uv workspace, Repository Guidelines, make dev-install, M0-M4 milestone exit gates, Claude working instructions (+1 more)

### Community 54 - "001_initial.sql"
Cohesion: 0.21
Nodes (10): approvals, capabilities, credentials, devices, invocations, pairing_codes, policy_grants, schema_version (+2 more)

### Community 55 - "Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect)"
Cohesion: 0.22
Nodes (9): device_offline error code, invocation_timeout error code, late_result error code (log-only), malformed_result error code, schema_drift error code (log-only), HDP Error Taxonomy (closed enumeration of error codes), Invocation Lifecycle (invoke->ack->result, cancel, late results, mid-call disconnect), HDP Message Types (hello, welcome, capabilities, invoke, ack, cancel, result, progress, revoke, heartbeat, error) (+1 more)

### Community 56 - "acceptance job"
Cohesion: 0.29
Nodes (8): acceptance job, check job, make acceptance, make check, CI workflow, oracle-docs M0-M4 plan, HermesDeviceProtocol, M4 real-Hermes acceptance

### Community 58 - "usb_bootstrap.py"
Cohesion: 0.13
Nodes (16): _b64(), _bootstrap_bytes(), _candidate_bytes(), OwnerAuthorizer, PrimaryNotifier, Protocol, RuntimeError, USB-only orchestration for a secondary-device enrollment. The bridge… (+8 more)

### Community 59 - "db.py"
Cohesion: 0.07
Nodes (27): _apply_pragmas(), _migrate(), Connection, RuntimeError, SQLite connection factory and forward-only migration runner (§3.1, §3.2)., The database's `schema_version` is higher than this build of `hdp_bridge` knows…, SchemaTooNewError, SQLite store helpers. (+19 more)

### Community 60 - "NodeConnection"
Cohesion: 0.13
Nodes (9): NodeConnection, Wraps one `aiohttp.web.WebSocketResponse` for the lifetime of one node…, Started alongside `run()`'s own read loop and reaped in that same `finally`, on…, Accept a signed decision only from the currently enrolled primary device., M2 auth (§3, §4.3): a `hello` must carry a credential — either an existing…, Every failed pairing handshake looks identical on the wire and charges the…, Refuse an opaque-token enrollment without touching legacy code state. USB…, A failed legacy-code proof burns its online-guessing budget. USB-enrollment and… (+1 more)

### Community 61 - "hdp-proto"
Cohesion: 0.80
Nodes (5): hdp-bridge, hdp-proto, hdp-reference-node, hermes-device-plugin, hermes-device-protocol

### Community 62 - "._read_loop"
Cohesion: 0.40
Nodes (5): _bridge_unavailable(), Future, StreamReader, Demultiplex every reply on one connection into the future that is waiting for…, _read_frame()

### Community 63 - "daemon.py"
Cohesion: 0.20
Nodes (8): AlreadyRunningError, RuntimeError, `hdp serve` — the foreground daemon entrypoint (§5.5). PID-file lifecycle…, Another live hdp-bridge process already holds this profile's PID file., HDP bridge daemon package., PolkitOwnerAuthorizer, Fresh local owner authorization through the host OS's Polkit/PAM stack., Use `pkexec` so HDP never reads or handles an owner password itself.

### Community 64 - "HDPApp"
Cohesion: 0.33
Nodes (8): HDPApp, Pilot coverage for the Textual operator dashboard., test_dashboard_explains_usb_enrollment(), test_dashboard_opens_the_paired_devices_screen(), test_dashboard_opens_the_pending_approvals_screen(), test_dashboard_starts_the_daemon_usb_bootstrap(), test_focused_menu_button_does_not_reverse_its_label(), test_selecting_a_device_sets_the_revoke_target()

### Community 65 - "Envelope"
Cohesion: 0.12
Nodes (10): Operator-only verb (`hermes hdp devices` at Task 17 was ultimately built…, Operator-only verb backing `hermes hdp audit` / `/hdp audit` — read-only, but…, Return daemon-memory approvals; none are durable while pending., _NodeSession, Any, Per-connection dispatch state: which invocation ids have been cancelled by the…, M2 (HDP-0.md Amendments (v0.2)): `revoke` is sent for real now — at M1 it was a…, Envelope (+2 more)

### Community 66 - "test_errors_conformance.py"
Cohesion: 0.43
Nodes (6): _parse_errors_md(), FR-32: `hdp-spec/errors.md` (the normative doc) must be identical to…, Catches the inverse drift: a code declared in errors.md but removed from…, test_errors_md_code_set_and_order_match_error_code(), test_errors_md_has_no_orphaned_entries(), test_errors_md_hints_match_hints_dict()

### Community 68 - "Android Node Contract"
Cohesion: 0.25
Nodes (7): Android lifecycle and security guidance, Android Node Contract, M6 bridge handoff, Protocol conformance target, Scope and first capability profile, State model, Wire contract

### Community 69 - "_InvokeRequestLike"
Cohesion: 0.22
Nodes (7): _InvokeRequestLike, Protocol, Challenge, InvokeMsg, Bridge → Node. `corr` (on the envelope, not here) carries the bridge-minted…, Bridge → Node (Amendments v0.4). A fresh nonce the node must sign to prove it…, test_invoke_msg_rejects_missing_deadline()

### Community 70 - "DeviceRoleManager"
Cohesion: 0.15
Nodes (16): DeviceRoleError, DeviceRoleManager, Connection, RuntimeError, Atomic role transitions for the single-primary sentinel model., Apply owner-authorized role changes without ever exposing two primaries., Promote an existing secondary, atomically demoting the old primary., Only a lone primary may be removed; otherwise a replacement must be promoted… (+8 more)

### Community 72 - "tests/conftest.py"
Cohesion: 0.50
Nodes (3): _hermes_home(), fixture, Test-wide fixtures for `hermes_device_plugin`. Real Hermes always sets…

### Community 73 - "test_scaffold.py"
Cohesion: 0.50
Nodes (3): Scaffold sanity tests., Keep `pytest` green before milestone implementation tests are added., test_scaffold_exists()

### Community 74 - "test_android_node.py"
Cohesion: 0.29
Nodes (9): M5 Android-shaped protocol conformance. The fixture is intentionally driven…, HDP-0.md Amendments v0.4 over a real socket: enrollment proves possession of…, The stolen-code case: presenting a valid pairing code alongside a public key…, Model the already-completed physical USB + local-owner ceremony for wire…, test_a_node_that_cannot_sign_the_challenge_never_pairs(), test_android_profile_is_device_bound_end_to_end(), test_android_profile_pair_invoke_reconnect_and_local_policy(), _usb_approved_enrollment() (+1 more)

### Community 75 - "SentinelApprovalRequest"
Cohesion: 0.40
Nodes (3): Deliver a host-signed secondary-enrollment prompt to the connected primary., Bridge → primary device: a host-signed request to add one secondary device., SentinelApprovalRequest

### Community 77 - "operations.py"
Cohesion: 0.19
Nodes (12): _error_detail(), pair_new(), PairingCodeRemovedError, RuntimeError, Operator-surface orchestration, owned by `hdp_bridge` and shared by both…, Send `ctl_devices_revoke` and return the daemon's reply envelope, or `None` if…, Human-readable pairing codes are not part of USB-sentinel enrollment., Reject the retired human-code flow. Pairing now starts only through a… (+4 more)

### Community 82 - "device_status.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `device.status@1` (hdp-spec/capabilities/device.status@1.md). Deliberately…

### Community 83 - "diagnostics.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `diagnostics.echo@1` (hdp-spec/capabilities/diagnostics.echo@1.md) — a pure…

### Community 84 - "notifications.py"
Cohesion: 0.50
Nodes (3): handle(), Any, `notifications.send@1` (hdp-spec/capabilities/notifications.send@1.md). Prints…

### Community 97 - "register_cli_command"
Cohesion: 0.29
Nodes (7): Any, Registers `hermes hdp {status,devices,pair,audit}` (design §2's confinement…, register_cli_command(), Any, Register the three device tools in toolset `device`, all `is_async=True`…, register(), test_register_cli_command_registers_hdp()

### Community 99 - "AuthFailed"
Cohesion: 0.19
Nodes (12): AuthFailed, descriptors_for_overrides(), Exception, The bridge rejected this node's credential. Deliberately **not** an `OSError`…, Build the advertised descriptor set for repeatable ``NAME@N`` CLI overrides.…, parametrize, M4 reference-node CLI overrides used by the multi-node lifecycle harness., test_capability_version_overrides_reject_invalid_values() (+4 more)

### Community 100 - "render_audit"
Cohesion: 0.50
Nodes (4): Calls `ctl_audit_tail` over the control socket rather than reading…, render_audit(), test_render_audit_against_a_real_daemon_contains_daemon_start(), test_render_audit_reports_unreachable_with_no_daemon()

### Community 102 - "test_messages.py"
Cohesion: 0.17
Nodes (13): _require_str_or_none(), parametrize, Amendments v0.3. Emitting the key as an explicit null (rather than omitting it)…, A pre-v0.3 node omits the key entirely; that must stay a valid `hello`, not a…, Optional, not untyped — same posture as a non-string `credential`., test_from_wire_tolerates_unknown_fields(), test_hello_platform_defaults_to_none_and_round_trips_present_as_null(), test_hello_rejects_malformed_hdp_versions() (+5 more)

### Community 104 - ".new"
Cohesion: 0.17
Nodes (22): read_frame(), write_frame(), control_request(), Make one operator control-plane request without importing the plugin transport., The demultiplexing contract `SocketTransport._read_loop` depends on: one rule…, `Server.close()` alone leaves already-accepted connections open — without this,…, Task 17 Step 2: `DeviceRecord.to_wire()` (Task 2) already carries `state`/…, Finding I4: `revoke_credential` used to return `None`, so a revoke that matched… (+14 more)

### Community 105 - "CancelMsg"
Cohesion: 0.33
Nodes (3): Best-effort — HDP-0.md §7: the caller has already removed the pending-table…, CancelMsg, Bridge → Node, sent best-effort on timeout or explicit cancellation.

## Knowledge Gaps
- **43 isolated node(s):** `schema_version`, `pairing_codes`, `policy_grants`, `approvals`, `invocations` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Registry` connect `Registry` to `test_control.py`, `ControlServer`, `PolicyTable`, `test_cli.py`, `ApprovalManager`, `Hello`, `CapabilityDescriptor`, `test_plugin_cli.py`, `control.py`, `_serve_claimed`, `test_server.py`, `tui.py`, `test_device_bound_pairing.py`, `AuditWriter`, `_FakeWS`, `NodeConnection`, `daemon.py`, `HDPApp`, `_InvokeRequestLike`, `Policy`, `test_ctl_list_approvals_returns_an_empty_pending_set`, `.new`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `Envelope` connect `Envelope` to `SocketTransport`, `Registry`, `AndroidNodeFixture`, `ControlServer`, `._handle`, `PolicyTable`, `test_cli.py`, `InprocTransport`, `Hello`, `CapabilityDescriptor`, `envelope.py`, `test_lifecycle.py`, `control.py`, `test_node_invocation_logging.py`, `test_server.py`, `test_device_bound_pairing.py`, `.from_wire`, `_FakeWS`, `NodeConnection`, `._read_loop`, `_InvokeRequestLike`, `_FakeControlServer`, `operations.py`, `AuthFailed`, `.new`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `NodeConnection` connect `NodeConnection` to `test_control.py`, `Registry`, `AndroidNodeFixture`, `ControlServer`, `PolicyTable`, `InvocationsMem`, `ApprovalManager`, `Hello`, `CapabilityDescriptor`, `test_lifecycle.py`, `control.py`, `_serve_claimed`, `Any`, `test_server.py`, `test_device_bound_pairing.py`, `EnrollmentCoordinator`, `.from_wire`, `AuditWriter`, `_FakeWS`, `daemon.py`, `Envelope`, `_InvokeRequestLike`, `SentinelApprovalRequest`, `CancelMsg`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `Registry` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Registry` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `NodeConnection` (e.g. with `AuditWriter` and `EnrollmentCoordinator`) actually correct?**
  _`NodeConnection` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `InvocationsMem` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`InvocationsMem` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `Envelope` (e.g. with `_InvokeRequestLike` and `NodeConnection`) actually correct?**
  _`Envelope` has 27 INFERRED edges - model-reasoned connections that need verification._