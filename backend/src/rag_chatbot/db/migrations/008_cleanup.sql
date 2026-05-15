-- Migration 008: drop dead columns from chat_logs
-- prompt_tokens and completion_tokens were reserved but never populated.
-- They will be re-added as a proper feature when token usage tracking
-- is wired end-to-end from the LLM response.

ALTER TABLE chat_logs
    DROP COLUMN IF EXISTS prompt_tokens,
    DROP COLUMN IF EXISTS completion_tokens;
