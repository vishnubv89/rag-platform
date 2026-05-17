CREATE TABLE IF NOT EXISTS document_labels (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    label_type  TEXT NOT NULL,
    label_value TEXT NOT NULL,
    UNIQUE(doc_id, label_type, label_value)
);
CREATE INDEX IF NOT EXISTS idx_document_labels_doc ON document_labels(doc_id);

CREATE TABLE IF NOT EXISTS user_attributes (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    attr_type   TEXT NOT NULL,
    attr_value  TEXT NOT NULL,
    synced_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, attr_type, attr_value)
);
CREATE INDEX IF NOT EXISTS idx_user_attributes_user ON user_attributes(user_id);
