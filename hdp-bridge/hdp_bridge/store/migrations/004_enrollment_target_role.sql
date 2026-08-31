ALTER TABLE pending_enrollments
    ADD COLUMN target_role TEXT NOT NULL DEFAULT 'secondary'
    CHECK (target_role IN ('primary', 'secondary'));

UPDATE schema_version SET version = 4;
