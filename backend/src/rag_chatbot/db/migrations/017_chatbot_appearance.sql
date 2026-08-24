ALTER TABLE chatbots
    ADD COLUMN IF NOT EXISTS accent_color TEXT NOT NULL DEFAULT '#D85A30',
    ADD COLUMN IF NOT EXISTS position     TEXT NOT NULL DEFAULT 'bottom-right'
        CHECK (position IN ('bottom-right', 'bottom-left'));
