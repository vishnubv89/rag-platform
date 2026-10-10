-- Google retired the Gemini 2.0 / 1.5 families (2.0 Flash: June 2026) and
-- text-embedding-004 (Jan 2026). Migration 001 seeded these into the default
-- org's app_config and the admin UI saved them into others, so existing rows
-- point at models that now return 404. Rewrite only the exact retired IDs;
-- anything an admin chose deliberately is left alone. Idempotent.
--
-- embedding_model is cosmetic here: the embedder reads the global setting
-- (gemini-embedding-2 @ 768 dims, matching vector(768)), never this row.

UPDATE app_config
   SET value = 'gemini-3.5-flash-lite', updated_at = now()
 WHERE key = 'llm_model'
   AND value IN (
       'gemini-2.0-flash', 'gemini-2.0-flash-lite',
       'gemini-1.5-flash', 'gemini-1.5-pro'
   );

UPDATE app_config
   SET value = 'models/gemini-embedding-2', updated_at = now()
 WHERE key = 'embedding_model'
   AND value IN ('text-embedding-004', 'models/text-embedding-004', 'models/gemini-embedding-001');
