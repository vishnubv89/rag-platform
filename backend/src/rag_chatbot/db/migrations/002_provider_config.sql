-- Add provider config keys to default org — safe to re-run

-- Fix embedding model name (text-embedding-004 was retired)
UPDATE app_config
SET    value = 'models/gemini-embedding-001'
WHERE  key = 'embedding_model'
AND    value = 'text-embedding-004';

INSERT INTO app_config (org_id, key, value)
SELECT o.id, cfg.key, cfg.value
FROM   organizations o,
       (VALUES
           ('llm_provider',     'gemini'),
           ('anthropic_model',  'claude-sonnet-4-6'),
           ('anthropic_api_key', '')
       ) AS cfg(key, value)
WHERE  o.slug = 'default'
ON CONFLICT (org_id, key) DO NOTHING;
