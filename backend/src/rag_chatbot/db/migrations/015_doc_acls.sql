-- Migration 015: document-level ACLs
-- By default all docs are public within their org (is_restricted = FALSE).
-- Flip is_restricted = TRUE on a doc to restrict it to explicit user grants.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS is_restricted BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS doc_permissions (
    id         BIGSERIAL PRIMARY KEY,
    doc_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (doc_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_permissions_doc  ON doc_permissions(doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_permissions_user ON doc_permissions(user_id);
