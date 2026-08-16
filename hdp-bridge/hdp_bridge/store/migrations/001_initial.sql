CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version (version) VALUES (1);

CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    friendly_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    client_version TEXT NOT NULL DEFAULT '',
    first_paired_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'revoked'
);

CREATE TABLE credentials (
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    credential_hash TEXT NOT NULL,
    issued_at INTEGER NOT NULL,
    revoked_at INTEGER
);

CREATE TABLE pairing_codes (
    code_hash TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    consumed_at INTEGER,
    issued_device_id TEXT
);

CREATE TABLE capabilities (
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    input_schema TEXT NOT NULL,
    output_schema TEXT NOT NULL,
    risk_class TEXT NOT NULL DEFAULT '',
    advertised_at INTEGER NOT NULL,
    PRIMARY KEY (device_id, name, version)
);

CREATE TABLE policy_grants (
    device_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    mode TEXT NOT NULL,
    scope TEXT NOT NULL,
    granted_at INTEGER NOT NULL,
    expires_at INTEGER,
    session_id TEXT,
    revoked_at INTEGER
);

CREATE TABLE approvals (
    invocation_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    version INTEGER NOT NULL,
    args_summary TEXT NOT NULL,
    requesting_session TEXT,
    risk_class TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    decided_at INTEGER,
    decided_by TEXT,
    scope TEXT
);

CREATE TABLE invocations (
    invocation_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    version INTEGER NOT NULL,
    state TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    dispatched_at INTEGER,
    completed_at INTEGER,
    error_code TEXT
);
