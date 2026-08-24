CREATE TABLE IF NOT EXISTS chatbots (
    id                 BIGSERIAL PRIMARY KEY,
    org_id             BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    description        TEXT,
    system_instruction TEXT,
    welcome_message    TEXT,
    key_hash           TEXT UNIQUE NOT NULL,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ DEFAULT now(),
    last_used          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chatbots_org      ON chatbots(org_id);
CREATE INDEX IF NOT EXISTS idx_chatbots_key_hash ON chatbots(key_hash);
