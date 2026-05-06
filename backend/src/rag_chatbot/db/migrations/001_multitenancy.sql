-- Multi-tenancy migration — safe to re-run (all statements are idempotent)

CREATE TABLE IF NOT EXISTS organizations (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    slug       TEXT NOT NULL UNIQUE,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO organizations (name, slug)
VALUES ('Default', 'default')
ON CONFLICT (slug) DO NOTHING;

-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS api_keys (
    id         BIGSERIAL PRIMARY KEY,
    org_id     BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key_hash   TEXT NOT NULL UNIQUE,
    label      TEXT NOT NULL DEFAULT '',
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    last_used  TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_org  ON api_keys(org_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_config (
    id         BIGSERIAL PRIMARY KEY,
    org_id     BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (org_id, key)
);

CREATE INDEX IF NOT EXISTS idx_app_config_org ON app_config(org_id);

INSERT INTO app_config (org_id, key, value)
SELECT o.id, cfg.key, cfg.value
FROM organizations o,
     (VALUES
        ('llm_model',        'gemini-2.0-flash'),
        ('embedding_model',  'text-embedding-004'),
        ('embedding_dim',    '768'),
        ('retrieval_top_k',  '8'),
        ('grader_max_loops', '3'),
        ('chunk_size',       '300'),
        ('chunk_overlap',    '50')
     ) AS cfg(key, value)
WHERE o.slug = 'default'
ON CONFLICT (org_id, key) DO NOTHING;

-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_logs (
    id                 BIGSERIAL PRIMARY KEY,
    org_id             BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_id         UUID NOT NULL,
    user_message       TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    source_chunk_ids   BIGINT[] DEFAULT '{}',
    loop_count         INT DEFAULT 0,
    prompt_tokens      INT DEFAULT 0,
    completion_tokens  INT DEFAULT 0,
    latency_ms         INT DEFAULT 0,
    created_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_logs_org     ON chat_logs(org_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created ON chat_logs(org_id, created_at DESC);

-- ----------------------------------------------------------------
-- Extend existing documents table with org_id (nullable for backwards compat)

ALTER TABLE documents ADD COLUMN IF NOT EXISTS org_id BIGINT REFERENCES organizations(id) ON DELETE SET NULL;

UPDATE documents d
SET    org_id = (SELECT id FROM organizations WHERE slug = 'default')
WHERE  d.org_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_documents_org ON documents(org_id);
