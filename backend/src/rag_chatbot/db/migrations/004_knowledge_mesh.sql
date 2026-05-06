-- Knowledge Mesh: connectors, sync jobs, health tables — safe to re-run

-- ── Connectors ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS connectors (
    id                    BIGSERIAL PRIMARY KEY,
    org_id                BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,
    connector_type        TEXT NOT NULL,  -- servicenow | sharepoint | confluence | manual
    config                JSONB NOT NULL DEFAULT '{}',
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    sync_interval_minutes INT NOT NULL DEFAULT 60,
    last_synced_at        TIMESTAMPTZ,
    last_sync_status      TEXT NOT NULL DEFAULT 'pending',  -- pending | running | success | error
    last_sync_message     TEXT,
    created_at            TIMESTAMPTZ DEFAULT now(),
    updated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_connectors_org ON connectors(org_id);
CREATE INDEX IF NOT EXISTS idx_connectors_next_sync
    ON connectors(is_active, last_synced_at, sync_interval_minutes)
    WHERE is_active = TRUE;

-- ── Sync Jobs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sync_jobs (
    id              BIGSERIAL PRIMARY KEY,
    connector_id    BIGINT NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'running',  -- running | success | error
    docs_added      INT NOT NULL DEFAULT 0,
    docs_updated    INT NOT NULL DEFAULT 0,
    docs_deleted    INT NOT NULL DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sync_jobs_connector ON sync_jobs(connector_id, started_at DESC);

-- ── Extend documents ─────────────────────────────────────────────────────────
ALTER TABLE documents ADD COLUMN IF NOT EXISTS connector_id    BIGINT REFERENCES connectors(id) ON DELETE SET NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS external_id     TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash    TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS last_synced_at  TIMESTAMPTZ;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS last_cited_at   TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_documents_connector
    ON documents(connector_id, external_id)
    WHERE connector_id IS NOT NULL;

-- ── Knowledge Conflicts ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_conflicts (
    id               BIGSERIAL PRIMARY KEY,
    org_id           BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    chunk_id_a       BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    chunk_id_b       BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    topic            TEXT,
    conflict_summary TEXT,
    status           TEXT NOT NULL DEFAULT 'pending',  -- pending | resolved | dismissed
    resolved_doc_id  BIGINT REFERENCES documents(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ DEFAULT now(),
    resolved_at      TIMESTAMPTZ,
    UNIQUE(chunk_id_a, chunk_id_b)
);

CREATE INDEX IF NOT EXISTS idx_conflicts_org_status ON knowledge_conflicts(org_id, status);

-- ── Knowledge Health view ────────────────────────────────────────────────────
CREATE OR REPLACE VIEW knowledge_health AS
SELECT
    d.org_id,
    COUNT(DISTINCT d.id)                                                        AS total_docs,
    COUNT(DISTINCT c.id)                                                        AS total_chunks,
    COUNT(DISTINCT CASE WHEN d.last_synced_at < now() - INTERVAL '90 days'
                         OR d.last_synced_at IS NULL THEN d.id END)            AS stale_docs,
    COUNT(DISTINCT kc.id) FILTER (WHERE kc.status = 'pending')                 AS open_conflicts,
    COUNT(DISTINCT conn.id) FILTER (WHERE conn.is_active)                      AS active_connectors,
    ROUND(
        100.0 * COUNT(DISTINCT d.id) FILTER (WHERE d.last_synced_at > now() - INTERVAL '90 days')
        / NULLIF(COUNT(DISTINCT d.id), 0)
    )                                                                           AS freshness_pct
FROM documents d
LEFT JOIN chunks c            ON c.doc_id = d.id
LEFT JOIN connectors conn     ON conn.id = d.connector_id
LEFT JOIN knowledge_conflicts kc
    ON kc.org_id = d.org_id
GROUP BY d.org_id;
