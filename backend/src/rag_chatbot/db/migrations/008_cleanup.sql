-- Migration 008: drop dead columns from chat_logs
-- prompt_tokens and completion_tokens were reserved but never populated.
-- They will be re-added as a proper feature when token usage tracking
-- is wired end-to-end from the LLM response.

-- NOTE: the DROP COLUMN that used to live here is intentionally gone.
-- run_schema() re-executes every migration file on every backend start (there
-- is no applied-migrations table), so dropping these columns here — only for
-- 013 to re-add them at DEFAULT 0 — erased all recorded token usage on every
-- restart. The columns are live now (see 013); 013 creates them when missing.
SELECT 1;
