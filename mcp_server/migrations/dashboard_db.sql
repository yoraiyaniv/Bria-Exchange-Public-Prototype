-- Bria Exchange Dashboard DB — users & API keys

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT        UNIQUE,
    password_hash TEXT,
    google_id     TEXT        UNIQUE,
    avatar_url    TEXT,
    display_name  TEXT,
    org_name      TEXT,
    role          TEXT        NOT NULL DEFAULT 'admin',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Safe migrations for existing databases
ALTER TABLE users ADD COLUMN IF NOT EXISTS org_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'admin';

CREATE INDEX IF NOT EXISTS idx_users_email     ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users (google_id);

CREATE TABLE IF NOT EXISTS api_keys (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    key_hash     TEXT        NOT NULL UNIQUE,
    key_prefix   TEXT        NOT NULL,
    label        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id   ON api_keys (user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash  ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys (is_active);

CREATE TABLE IF NOT EXISTS agents (
    id           TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id      BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name         TEXT        NOT NULL,
    type         TEXT        NOT NULL DEFAULT 'AI Agent',
    owner        TEXT        NOT NULL,
    policy       JSONB       NOT NULL DEFAULT '{}',
    notification_override JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE agents ADD COLUMN IF NOT EXISTS api_key TEXT UNIQUE;

CREATE INDEX IF NOT EXISTS idx_agents_user_id ON agents (user_id);
CREATE INDEX IF NOT EXISTS idx_agents_api_key ON agents (api_key);

CREATE TABLE IF NOT EXISTS connected_sources (
    id              TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id         BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    connector_id    TEXT        NOT NULL,
    name            TEXT        NOT NULL,
    domain          TEXT        NOT NULL,
    authority_level TEXT        NOT NULL,
    api_key         TEXT,
    status          TEXT        NOT NULL DEFAULT 'active',
    last_tested_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, connector_id)
);

CREATE INDEX IF NOT EXISTS idx_connected_sources_user_id ON connected_sources (user_id);

CREATE TABLE IF NOT EXISTS source_interests (
    id              TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    connector_id    TEXT        NOT NULL,
    user_id         BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    notify_on_launch BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (connector_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_source_interests_connector ON source_interests (connector_id);
CREATE INDEX IF NOT EXISTS idx_source_interests_user_id   ON source_interests (user_id);

CREATE TABLE IF NOT EXISTS custom_sources (
    id              TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id         BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    description     TEXT,
    source_type     TEXT        NOT NULL,   -- 'url' | 'api' | 'file'
    domain          TEXT        NOT NULL,
    authority_level TEXT        NOT NULL DEFAULT 'secondary',
    scope           TEXT        NOT NULL DEFAULT 'private',  -- 'private' | 'public'
    connection_config JSONB     NOT NULL DEFAULT '{}',
    extracted_text  TEXT,                   -- never sent to client
    status          TEXT        NOT NULL DEFAULT 'pending',  -- 'pending' | 'active' | 'error'
    error_message   TEXT,
    last_indexed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_sources_user_id ON custom_sources (user_id);
CREATE INDEX IF NOT EXISTS idx_custom_sources_scope   ON custom_sources (scope);
