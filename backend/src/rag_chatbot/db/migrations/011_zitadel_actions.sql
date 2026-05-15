-- Migration 011: Zitadel Action claim enrichment support
-- Adds default_role to org_domains and per-user role overrides table.
-- Safe to re-run (idempotent).

-- Default role for every user whose email domain matches this org.
-- Typically "member"; promote specific users via sso_user_roles.
ALTER TABLE org_domains
    ADD COLUMN IF NOT EXISTS default_role TEXT NOT NULL DEFAULT 'member';

-- Per-user role override for SSO users.
-- Row here beats the domain default_role.
-- email is lowercased on insert.
CREATE TABLE IF NOT EXISTS sso_user_roles (
    email      TEXT PRIMARY KEY,          -- lowercase SSO email
    org_id     BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sso_user_roles_org ON sso_user_roles(org_id);

-- Seed: make the first user of each org an admin by default
INSERT INTO sso_user_roles (email, org_id, role) VALUES
    ('alice@excel.com',  70, 'admin'),
    ('carol@marvel.com', 71, 'admin'),
    ('eve@prime.com',    72, 'admin'),
    ('grace@wonder.com', 73, 'admin')
ON CONFLICT (email) DO NOTHING;
