"""
Knowledge Mesh API — application entry point.

Assembles the FastAPI application: middleware, CORS, rate limiting,
exception handlers, and router registration. Business logic lives in
api/routers/; data access in db/repositories/; schemas in api/schemas.py.
"""

import logging
import tempfile
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from rag_chatbot.api.admin_router import router as admin_router
from rag_chatbot.api.rate_limit import limiter, rate_limit_exceeded_handler
from rag_chatbot.api.routers.chat import router as chat_router
from rag_chatbot.api.routers.curate import router as curate_router
from rag_chatbot.api.routers.sessions import router as sessions_router
from rag_chatbot.api.routers.suggest import router as suggest_router
from rag_chatbot.api.schemas import IngestResponse, IngestTextRequest
from rag_chatbot.api.zitadel_enrich import router as enrich_router
from rag_chatbot.auth.router import router as auth_router
from rag_chatbot.config import settings
from rag_chatbot.connectors.sync_engine import start_scheduler, stop_scheduler
from rag_chatbot.db.connection import close_pool, run_schema
from rag_chatbot.ingestion.pipeline import ingest_file, ingest_text
from rag_chatbot.observability import init_datadog, init_otel

_rag_log = logging.getLogger("rag_chatbot")
_rag_log.setLevel(logging.INFO)
if not _rag_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _rag_log.addHandler(_h)

logger = logging.getLogger(__name__)


def _is_valid_uuid(value: str) -> bool:
    """Return True if value is a well-formed UUID string."""
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks (schema migration, observability init) then teardown."""
    await run_schema()
    init_datadog()
    init_otel()
    start_scheduler()
    yield
    stop_scheduler()
    await close_pool()


app = FastAPI(
    title="Agentic RAG Chatbot",
    description="LangGraph + FastMCP + pgvector + Gemini",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(enrich_router)  # /internal/zitadel/enrich — internal only
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(curate_router)
app.include_router(suggest_router)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Log full traceback server-side; return sanitised message to client."""
    logger.error(
        "Unhandled %s %s\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


@app.get("/health")
async def health() -> dict:
    """Return service liveness status."""
    return {"status": "ok"}


@app.post("/ingest/text", response_model=IngestResponse)
async def ingest_text_endpoint(req: IngestTextRequest) -> IngestResponse:
    """Ingest a plain-text document into the knowledge base."""
    try:
        result = await ingest_text(text=req.text, title=req.title, source=req.source)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error") from e
    return IngestResponse(**result)


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file_endpoint(file: UploadFile = File(...)) -> IngestResponse:
    """Ingest an uploaded file (PDF, DOCX, TXT) into the knowledge base."""
    suffix = Path(file.filename or "upload").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = await ingest_file(tmp_path, title=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return IngestResponse(**result)
