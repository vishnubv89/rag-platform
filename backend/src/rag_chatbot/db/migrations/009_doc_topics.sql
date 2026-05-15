-- Migration 009: cache LLM-extracted topics per document
-- topics is a JSONB array: [{"label": str, "subtopics": [str], "color": str}]
-- NULL means not yet computed; an empty array means computed but no topics found.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS topics JSONB DEFAULT NULL;
