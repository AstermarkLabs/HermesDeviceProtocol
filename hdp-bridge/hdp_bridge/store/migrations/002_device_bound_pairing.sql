-- HDP-0.md Amendments (v0.4): six-digit pairing codes, a hard attempt budget, and
-- device-bound authentication.
--
-- The code shrank from 128 bits to ~20 (1,000,000 possibilities), so entropy alone no
-- longer bounds an online guesser. `attempts_remaining` does: every failed pairing attempt
-- burns one from every live code, and at zero the code is permanently invalidated via
-- `invalidated_at` — destroyed, not cooled down. That caps a guesser at a handful of tries
-- per pairing window regardless of how fast they can connect.
--
-- `device_pubkey` stores the node's EC P-256 public key (base64 DER SubjectPublicKeyInfo),
-- captured at pairing after a challenge-response proves possession of the private half.
-- Empty string means a node that predates v0.4 and authenticates by credential alone.

UPDATE schema_version SET version = 2;

ALTER TABLE pairing_codes ADD COLUMN attempts_remaining INTEGER NOT NULL DEFAULT 5;
ALTER TABLE pairing_codes ADD COLUMN invalidated_at INTEGER;

ALTER TABLE devices ADD COLUMN device_pubkey TEXT NOT NULL DEFAULT '';
