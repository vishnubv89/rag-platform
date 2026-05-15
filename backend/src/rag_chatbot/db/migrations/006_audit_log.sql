CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    org_id      BIGINT REFERENCES organizations(id) ON DELETE SET NULL,
    user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,         -- e.g. "create", "delete", "sync", "login"
    resource    TEXT NOT NULL,         -- e.g. "document", "user", "connector"
    resource_id TEXT,                  -- string ID of the affected resource
    detail      JSONB DEFAULT '{}'::jsonb,
    ip          TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_org ON audit_logs (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id, created_at DESC);
