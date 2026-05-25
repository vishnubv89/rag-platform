-- Migration 014: embed tokens for the JS chat widget
-- Each token is org-scoped, rate-limited, and revocable from the admin panel.
-- The raw token is shown once on creation; only the SHA-256 hash is stored.

CREATE TABLE IF NOT EXISTS embed_tokens (
    id          BIGSERIAL PRIMARY KEY,
    org_id      BIGINT  NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,          -- human label, e.g. "Support portal"
    token_hash  TEXT    NOT NULL UNIQUE,   -- SHA-256(raw_token)
    created_at  TIMESTAMPTZ DEFAULT now(),
    revoked_at  TIMESTAMPTZ               -- NULL = active
);

CREATE INDEX IF NOT EXISTS idx_embed_tokens_org ON embed_tokens(org_id);
