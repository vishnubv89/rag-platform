-- Add NVIDIA / OpenAI-compatible provider config keys — safe to re-run

INSERT INTO app_config (org_id, key, value)
SELECT o.id, cfg.key, cfg.value
FROM   organizations o,
       (VALUES
           ('nvidia_api_key',  ''),
           ('nvidia_model',    'meta/llama-3.1-405b-instruct'),
           ('nvidia_base_url', 'https://integrate.api.nvidia.com/v1')
       ) AS cfg(key, value)
WHERE  o.slug = 'default'
ON CONFLICT (org_id, key) DO NOTHING;
