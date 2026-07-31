CREATE TABLE IF NOT EXISTS exchange_results (
    id                   TEXT PRIMARY KEY,
    user_id              TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    source_url           TEXT,
    publication          TEXT,
    input_text           TEXT NOT NULL,
    full_response        JSONB NOT NULL,
    verified_claim_count INT NOT NULL DEFAULT 0,
    verdict              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exchange_results_user
    ON exchange_results(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_exchange_results_created
    ON exchange_results(created_at DESC);

CREATE TABLE IF NOT EXISTS exchange_usage (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT,
    ip_address      TEXT,
    month           TEXT NOT NULL,
    verified_claims INT NOT NULL DEFAULT 0,
    UNIQUE(user_id, month),
    UNIQUE(ip_address, month)
);
