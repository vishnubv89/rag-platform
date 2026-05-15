-- Migration 010: org_domains table + RBAC helpers
-- Safe to re-run (idempotent)

-- Email-domain → org mapping.
-- When an SSO user has no custom org claim, their email domain is matched here.
CREATE TABLE IF NOT EXISTS org_domains (
    domain  TEXT PRIMARY KEY,
    org_id  BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_org_domains_org ON org_domains(org_id);

-- Seed domains for the 4 tenant orgs
INSERT INTO org_domains (domain, org_id)
SELECT 'excel.com',  o.id FROM organizations o WHERE o.slug = 'excel'
ON CONFLICT (domain) DO NOTHING;

INSERT INTO org_domains (domain, org_id)
SELECT 'marvel.com', o.id FROM organizations o WHERE o.slug = 'marvel'
ON CONFLICT (domain) DO NOTHING;

INSERT INTO org_domains (domain, org_id)
SELECT 'prime.com',  o.id FROM organizations o WHERE o.slug = 'prime'
ON CONFLICT (domain) DO NOTHING;

INSERT INTO org_domains (domain, org_id)
SELECT 'wonder.com', o.id FROM organizations o WHERE o.slug = 'wonder'
ON CONFLICT (domain) DO NOTHING;
