-- USB Sentinel Pairing: device roles, pending device-bound enrollment, and the
-- profile-wide containment lock created by a primary device's Block decision.

UPDATE schema_version SET version = 3;

ALTER TABLE devices ADD COLUMN role TEXT NOT NULL DEFAULT 'secondary'
    CHECK (role IN ('primary', 'secondary'));

CREATE UNIQUE INDEX one_primary_device ON devices(role) WHERE role = 'primary';

CREATE TABLE pending_enrollments (
    identifier_hash TEXT PRIMARY KEY,
    host_key_fingerprint TEXT NOT NULL,
    candidate_key_fingerprint TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'pending', 'candidate_approved', 'primary_approved', 'consumed', 'denied', 'blocked', 'expired'
    )),
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    candidate_approved_at INTEGER,
    primary_approved_at INTEGER,
    primary_device_id TEXT REFERENCES devices(device_id),
    consumed_at INTEGER
);

CREATE TABLE pairing_locks (
    profile_lock INTEGER PRIMARY KEY CHECK (profile_lock = 1),
    locked_at INTEGER NOT NULL,
    blocked_by_device_id TEXT REFERENCES devices(device_id)
);
