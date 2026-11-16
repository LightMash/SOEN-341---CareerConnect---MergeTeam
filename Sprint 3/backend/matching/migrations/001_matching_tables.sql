-- Qualification matching: three new tables. Existing tables are not changed.
-- Safe to run more than once (IF NOT EXISTS everywhere).
-- Needs PostgreSQL 15+ for NULLS NOT DISTINCT.
-- Mirrors matching/models.py; keep the two in sync.

CREATE TABLE IF NOT EXISTS custom_qualifications (
    id              SERIAL PRIMARY KEY,
    category        VARCHAR(20)  NOT NULL,
    name            VARCHAR(120) NOT NULL,
    normalized_name VARCHAR(120) NOT NULL,
    field           VARCHAR(60),
    created_by      INTEGER      NOT NULL REFERENCES users (id),
    created_at      TIMESTAMP    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT uq_custom_qualification UNIQUE NULLS NOT DISTINCT (category, normalized_name, field),
    CONSTRAINT ck_custom_qualification_category
        CHECK (category IN ('degree', 'license', 'certification', 'language', 'skill'))
);

CREATE INDEX IF NOT EXISTS ix_custom_qualifications_id ON custom_qualifications (id);

CREATE TABLE IF NOT EXISTS seeker_qualifications (
    seeker_id         INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    qualification_key VARCHAR(120) NOT NULL,
    source            VARCHAR(30)  NOT NULL DEFAULT 'manual',
    created_at        TIMESTAMP    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT pk_seeker_qualifications PRIMARY KEY (seeker_id, qualification_key),
    CONSTRAINT ck_seeker_qualification_source
        CHECK (source IN ('manual', 'resume_scan', 'reviewer_suggestion'))
);

CREATE TABLE IF NOT EXISTS listing_requirements (
    listing_id        INTEGER      NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    qualification_key VARCHAR(120) NOT NULL,
    is_required       BOOLEAN      NOT NULL DEFAULT TRUE,
    weight            INTEGER      NOT NULL DEFAULT 1,
    CONSTRAINT pk_listing_requirements PRIMARY KEY (listing_id, qualification_key),
    CONSTRAINT ck_listing_requirement_weight CHECK (weight BETWEEN 1 AND 3)
);
