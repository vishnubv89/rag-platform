-- Migration 007: add feedback column to chat_logs
-- feedback: 1 = thumbs up, -1 = thumbs down, NULL = no feedback given

ALTER TABLE chat_logs
    ADD COLUMN IF NOT EXISTS feedback SMALLINT
        CHECK (feedback IN (1, -1));
