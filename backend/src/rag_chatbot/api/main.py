from contextlib import asynccontextmanager
from pathlib import Path
import tempfile
import time
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag_chatbot.config import settings
from rag_chatbot.db.connection import run_schema, close_pool, get_pool
from rag_chatbot.agent.graph import rag_graph
from rag_chatbot.ingestion.pipeline import ingest_file, ingest_text
from rag_chatbot.api.admin_router import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_schema()
    yield
    await close_pool()


app = FastAPI(
    title="Agentic RAG Chatbot",
    description="LangGraph + FastMCP + pgvector + Gemini",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router, prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    org_id: int | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    source_chunk_ids: list[int]
    sources: list[dict]
    loop_count: int
    session_id: str


class IngestTextRequest(BaseModel):
    title: str
    text: str
    source: str = ""


class IngestResponse(BaseModel):
    doc_id: int
    title: str
    chunks: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid4())
    messages = req.history + [{"role": "user", "content": req.message}]
    initial_state = {
        "messages": messages,
        "query": req.message,
        "retrieved_docs": [],
        "grading_passed": False,
        "loop_count": 0,
        "answer": "",
        "source_chunk_ids": [],
        "sources": [],
        "skip_retrieval": False,
        "llm_config": {},
    }
    # Fetch org config to drive provider/model selection at runtime
    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = req.org_id or await conn.fetchval(
            "SELECT id FROM organizations WHERE slug='default'"
        )
        rows = await conn.fetch(
            "SELECT key, value FROM app_config WHERE org_id=$1", org_id
        ) if org_id else []
    llm_config = {r["key"]: r["value"] for r in rows}

    t0 = time.monotonic()
    try:
        final_state = await rag_graph.ainvoke(initial_state | {"llm_config": llm_config})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    latency_ms = int((time.monotonic() - t0) * 1000)

    async with pool.acquire() as conn:
        if org_id is not None:
            await conn.execute(
                """
                INSERT INTO chat_logs
                    (org_id, session_id, user_message, assistant_response,
                     source_chunk_ids, loop_count, latency_ms)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                org_id,
                UUID(session_id),
                req.message,
                final_state["answer"],
                final_state["source_chunk_ids"],
                final_state["loop_count"],
                latency_ms,
            )

    return ChatResponse(
        answer=final_state["answer"],
        source_chunk_ids=final_state["source_chunk_ids"],
        sources=final_state.get("sources", []),
        loop_count=final_state["loop_count"],
        session_id=session_id,
    )


@app.post("/ingest/text", response_model=IngestResponse)
async def ingest_text_endpoint(req: IngestTextRequest):
    try:
        result = await ingest_text(
            text=req.text, title=req.title, source=req.source
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return IngestResponse(**result)


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "upload").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = await ingest_file(tmp_path, title=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return IngestResponse(**result)


@app.get("/health")
async def health():
    return {"status": "ok"}
