-- Bria Exchange MCP DB — request logging schema

CREATE TABLE IF NOT EXISTS requests (
    id                   BIGSERIAL PRIMARY KEY,
    api_key              TEXT,
    tool                 TEXT        NOT NULL,
    request_id           TEXT        NOT NULL UNIQUE,
    content              TEXT        NOT NULL,
    input_hash           TEXT        NOT NULL,
    decision             TEXT        NOT NULL,
    vs                   NUMERIC(6,4),
    ecr                  NUMERIC(6,4),
    sci                  NUMERIC(6,4),
    total_claims         INTEGER     NOT NULL DEFAULT 0,
    corroborated_count   INTEGER     NOT NULL DEFAULT 0,
    contradicted_count   INTEGER     NOT NULL DEFAULT 0,
    unsupported_count    INTEGER     NOT NULL DEFAULT 0,
    out_of_scope_count   INTEGER     NOT NULL DEFAULT 0,
    elapsed_seconds      NUMERIC(10,3),
    model                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_requests_api_key   ON requests (api_key);
CREATE INDEX IF NOT EXISTS idx_requests_decision  ON requests (decision);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests (created_at);

CREATE TABLE IF NOT EXISTS claims (
    id          BIGSERIAL PRIMARY KEY,
    request_id  TEXT        NOT NULL REFERENCES requests (request_id) ON DELETE CASCADE,
    claim_id    TEXT        NOT NULL,
    text        TEXT        NOT NULL,
    claim_type  TEXT,
    status      TEXT        NOT NULL,
    confidence  NUMERIC(5,4),
    reasoning   TEXT,
    UNIQUE (request_id, claim_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_request_id ON claims (request_id);
CREATE INDEX IF NOT EXISTS idx_claims_status     ON claims (status);

CREATE TABLE IF NOT EXISTS citations (
    id         BIGSERIAL PRIMARY KEY,
    claim_id   BIGINT      NOT NULL REFERENCES claims (id) ON DELETE CASCADE,
    source     TEXT,
    identifier TEXT,
    date       TEXT,
    value      TEXT,
    label      TEXT
);

CREATE INDEX IF NOT EXISTS idx_citations_claim_id ON citations (claim_id);

-- Review workflow fields (added via safe ALTER)
ALTER TABLE requests ADD COLUMN IF NOT EXISTS review_status    TEXT        NOT NULL DEFAULT 'not_required';
ALTER TABLE requests ADD COLUMN IF NOT EXISTS reviewed_by      TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS reviewed_at      TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS review_note      TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS review_actions   JSONB;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS corrected_text   TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS agent_id         TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS parent_request_id TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS domain           TEXT        NOT NULL DEFAULT 'financial';
ALTER TABLE requests ADD COLUMN IF NOT EXISTS decision_reasons JSONB;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS full_response    JSONB;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS config           JSONB;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS trace_id         TEXT;

CREATE INDEX IF NOT EXISTS idx_requests_review_status ON requests (review_status);
CREATE INDEX IF NOT EXISTS idx_requests_agent_id      ON requests (agent_id);
