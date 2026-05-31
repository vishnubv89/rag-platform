"""
Request/response schemas for the Knowledge Mesh API.

All Pydantic models used by route handlers live here. Import from this
module rather than from individual router files to avoid circular imports.
"""

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Chat schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for /chat and /chat/stream endpoints."""

    message: str
    history: list[dict] = []
    org_id: int | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response body for the non-streaming /chat endpoint."""

    answer: str
    source_chunk_ids: list[int]
    sources: list[dict]
    loop_count: int
    session_id: str


class FeedbackRequest(BaseModel):
    """Thumbs-up / thumbs-down feedback on a chat log entry."""

    value: int  # 1 = thumbs up, -1 = thumbs down


# ---------------------------------------------------------------------------
# Follow-up schemas
# ---------------------------------------------------------------------------

class FollowUpRequest(BaseModel):
    """Request body for /chat/followup — generate follow-up questions."""

    messages: list[dict]
    org_id: int | None = None


class FollowUpResponse(BaseModel):
    """Three suggested follow-up questions for the given conversation."""

    suggestions: list[str]


# ---------------------------------------------------------------------------
# Suggest schemas
# ---------------------------------------------------------------------------

class SuggestRequest(BaseModel):
    """Request body for /suggest — next-paragraph writing assistance."""

    context: str
    org_id: int | None = None


class SuggestResponse(BaseModel):
    """Suggested continuation text and the KB chunks used as reference."""

    suggestion: str
    sources: list[dict]


# ---------------------------------------------------------------------------
# Curate schemas
# ---------------------------------------------------------------------------

class CurateRequest(BaseModel):
    """Request body for /curate — KCS/ITIL knowledge article improvement."""

    title: str = ""
    content: str
    org_id: int | None = None


class CurateChange(BaseModel):
    """A single quality-dimension improvement applied during curation."""

    dimension: str
    description: str


class CurateResponse(BaseModel):
    """Full curation result: improved document, change log, and quality scores."""

    improved_title: str
    improved_content: str
    changes: list[CurateChange]
    score_before: int
    score_after: int
    sources: list[dict]


class SNCategory(BaseModel):
    """A ServiceNow KB category (sys_id + display label)."""

    sys_id: str
    label: str


class CurateSyncRequest(BaseModel):
    """Request body for /curate/sync — write a curated article to ServiceNow."""

    title: str
    content: str
    category_sys_id: str
    publish: bool = False
    external_id: str | None = None   # existing SN sys_id → PATCH; None → POST
    org_id: int | None = None


class CurateSyncResponse(BaseModel):
    """Result of the ServiceNow write-back operation."""

    sys_id: str
    url: str
    action: str   # "created" | "updated"


# ---------------------------------------------------------------------------
# Ingest schemas
# ---------------------------------------------------------------------------

class IngestTextRequest(BaseModel):
    """Request body for /ingest/text — ingest a plain-text document."""

    title: str
    text: str
    source: str = ""


class IngestResponse(BaseModel):
    """Result of a document ingestion operation."""

    doc_id: int
    title: str
    chunks: int
