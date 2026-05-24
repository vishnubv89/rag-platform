-- Migration 013: re-add token usage columns to chat_logs
-- Dropped in 008_cleanup.sql when they were unpopulated dead columns.
-- Now properly wired: generate_with_usage() + stream_generate(usage_out=)
-- populate these from every LLM call through AgentState accumulators.

ALTER TABLE chat_logs
    ADD COLUMN IF NOT EXISTS prompt_tokens    INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS completion_tokens INT NOT NULL DEFAULT 0;
