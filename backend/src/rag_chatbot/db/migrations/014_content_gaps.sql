-- Migration 014: track which agent node handled each request
ALTER TABLE chat_logs
    ADD COLUMN IF NOT EXISTS answer_type TEXT DEFAULT 'generator'
        CHECK (answer_type IN ('generator','chitchat','kb_overview','clarify','action'));

CREATE INDEX IF NOT EXISTS idx_chat_logs_answer_type
    ON chat_logs(org_id, answer_type)
    WHERE answer_type = 'clarify';
