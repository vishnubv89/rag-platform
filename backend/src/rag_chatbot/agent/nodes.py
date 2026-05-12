"""
LangGraph node functions for the Agentic RAG loop.

Flow: intent → retriever → grader → generator
                         ↘ rewriter → retriever (loop, max grader_max_loops)
      intent (greeting)  → generator  (skip retrieval entirely)
"""
import asyncio
import json
import re

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.runnables import RunnableConfig

from rag_chatbot.db.connection import get_pool
from rag_chatbot.llm.client import generate as _generate, stream_generate as _stream_generate
from rag_chatbot.retrieval.vector_store import hybrid_search
from rag_chatbot.agent.state import AgentState


# ---------------------------------------------------------------------------
# Intent — lightweight keyword check, no LLM call
# ---------------------------------------------------------------------------

_KB_OVERVIEW_RE = re.compile(
    r"(summarize|summary|list|overview|what.*(document|topic|know|cover|help)|"
    r"show.*document|what.*knowledge.base|what.*in.*kb|what.*can.*you.*help)",
    re.IGNORECASE,
)

_CHITCHAT_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|howdy|greetings|good\s*(morning|afternoon|evening|day)|"
    r"what'?s\s+up|sup|yo+|hiya|how\s+are\s+you|how\s+do\s+you\s+do|nice\s+to\s+meet\s+you|"
    r"thanks?(\s+you)?|thank\s+you|bye+|goodbye|see\s+you|take\s+care|"
    r"who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do)\W*$",
    re.IGNORECASE,
)


async def intent_node(state: AgentState) -> dict:
    query = state["messages"][-1]["content"].strip()
    is_chitchat = bool(_CHITCHAT_RE.match(query))
    is_overview = bool(_KB_OVERVIEW_RE.search(query)) and not is_chitchat
    return {
        "skip_retrieval": is_chitchat or is_overview,
        "kb_overview": is_overview,
    }


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

async def retriever_node(state: AgentState) -> dict:
    docs = await hybrid_search(state["query"], org_id=state.get("org_id"))
    return {"retrieved_docs": docs}


# ---------------------------------------------------------------------------
# Grader — single batch LLM call instead of N parallel calls
# ---------------------------------------------------------------------------

_GRADER_SYSTEM = (
    "You are a relevance grader. Given a query and numbered document chunks, "
    "respond with ONLY a JSON array of integer indices (0-based) of chunks that "
    "directly address the query topic or contain facts needed to answer it. "
    "Include a chunk if it is on the same topic as the query. "
    "Exclude a chunk if it is about a different subject — even if it shares some words. "
    "Examples: query 'reset password' → include chunks about passwords/accounts, "
    "exclude chunks about Excel or cookies. "
    "[] means no chunks are relevant. "
    "No explanation — just the JSON integer array."
)


def _parse_indices(text: str, n_docs: int) -> list[int]:
    """Extract relevant indices from the LLM response, handling multiple formats."""
    # Try pure integer array first: [0, 2]
    m = re.search(r"\[[\d,\s]*\]", text)
    if m:
        try:
            indices = json.loads(m.group())
            valid = [i for i in indices if isinstance(i, int) and 0 <= i < n_docs]
            if valid or m.group().strip() == "[]":
                return valid
        except json.JSONDecodeError:
            pass

    # Fallback: extract any standalone integers that look like indices
    numbers = [int(x) for x in re.findall(r"\b(\d+)\b", text) if int(x) < n_docs]
    return list(dict.fromkeys(numbers))  # deduplicate, preserve order


async def grader_node(state: AgentState) -> dict:
    query = state["query"]
    docs = state["retrieved_docs"]
    cfg = state.get("llm_config", {})

    if not docs:
        return {"grading_passed": False, "loop_count": state["loop_count"] + 1}

    doc_list = "\n".join(f"[{i}] {d['text'][:600]}" for i, d in enumerate(docs))
    prompt = f"Query: {query}\n\nDocuments:\n{doc_list}"

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None, lambda: _generate(prompt, _GRADER_SYSTEM, cfg)
    )

    relevant_indices = _parse_indices(response, len(docs))
    relevant_docs = [docs[i] for i in relevant_indices] if relevant_indices else []
    passed = len(relevant_docs) > 0

    return {
        "retrieved_docs": relevant_docs if passed else [],
        "grading_passed": passed,
        "loop_count": state["loop_count"] + 1,
    }


# ---------------------------------------------------------------------------
# Rewriter
# ---------------------------------------------------------------------------

_REWRITER_SYSTEM = (
    "You are a query rewriting assistant. The initial query failed to retrieve "
    "useful documents. Rewrite it to be more specific or use different keywords. "
    "Respond with ONLY the rewritten query."
)


async def rewriter_node(state: AgentState) -> dict:
    cfg = state.get("llm_config", {})
    loop = asyncio.get_running_loop()
    new_query = await loop.run_in_executor(
        None,
        lambda: _generate(f"Original query: {state['query']}", _REWRITER_SYSTEM, cfg),
    )
    return {"query": new_query}


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

async def _stream_llm(
    prompt: str, system: str, cfg: dict, config: RunnableConfig
) -> str:
    """Run stream_generate in a thread, dispatch each token as a custom event,
    and return the full accumulated text."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    chunks: list[str] = []

    def _run() -> None:
        try:
            for chunk in _stream_generate(prompt, system, cfg):
                chunks.append(chunk)
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    fut = loop.run_in_executor(None, _run)

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        await adispatch_custom_event("stream_token", {"token": chunk}, config=config)

    await fut
    return "".join(chunks)


# ---------------------------------------------------------------------------
# KB Overview — fires when user asks what's in the knowledge base
# ---------------------------------------------------------------------------

_KB_OVERVIEW_SYSTEM = (
    "You are a helpful assistant. The user wants to know what topics their "
    "knowledge base covers. Based ONLY on the document titles listed below, "
    "write a concise, friendly overview that groups related documents into "
    "themes. Use bullet points for the themes. Do not invent topics not "
    "reflected in the titles. End with a one-line offer to answer specific questions."
)


async def kb_overview_node(state: AgentState, config: RunnableConfig) -> dict:
    """Fetch all doc titles for the org and summarise them — no retrieval needed."""
    org_id = state.get("org_id")
    cfg = state.get("llm_config", {})

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT title
               FROM documents
               WHERE ($1::bigint IS NULL OR org_id = $1)
                 AND (SELECT COUNT(*) FROM chunks WHERE doc_id = documents.id) > 0
               ORDER BY title""",
            org_id,
        )

    if not rows:
        answer = (
            "Your knowledge base is currently empty — no documents have been "
            "ingested yet. Upload files or connect a data source to get started."
        )
        return {
            "answer": answer,
            "source_chunk_ids": [],
            "sources": [],
            "messages": [{"role": "assistant", "content": answer}],
        }

    doc_list = "\n".join(f"- {r['title']}" for r in rows)
    prompt = (
        f"Here are the {len(rows)} documents in the knowledge base:\n\n"
        f"{doc_list}\n\n"
        "Provide a concise overview of the topics covered, grouping related documents."
    )

    answer = await _stream_llm(prompt, _KB_OVERVIEW_SYSTEM, cfg, config)

    return {
        "answer": answer,
        "source_chunk_ids": [],
        "sources": [],
        "messages": [{"role": "assistant", "content": answer}],
    }


_GENERATOR_SYSTEM = (
    "You are a knowledgeable assistant. Answer the user's question using ONLY the "
    "context provided. Answer directly and conversationally — never mention that you "
    "are working from documents, chunks, context, or retrieved information. "
    "Do not use phrases like 'based on the provided', 'according to the documents', "
    "'the context states', or anything similar. "
    "IMPORTANT: Do NOT use your general knowledge to fill gaps. If the provided context "
    "does not contain the answer, say 'I don't have information about that in my knowledge base.' "
    "Do not invent, guess, or supplement with facts not present in the context."
)

_CHITCHAT_SYSTEM = "You are a helpful and friendly assistant."


async def generator_node(state: AgentState, config: RunnableConfig) -> dict:
    query = state["messages"][-1]["content"]
    docs = state["retrieved_docs"]
    cfg = state.get("llm_config", {})
    skip = state.get("skip_retrieval", False)

    if skip or not docs:
        prompt = query
        system = _CHITCHAT_SYSTEM
    else:
        context = "\n\n".join(
            f"[Source: {d.get('doc_title') or 'Unknown'} | chunk {d['chunk_id']}]\n{d['text']}"
            for d in docs
        )
        prompt = f"Question: {query}\n\nContext:\n{context}"
        system = _GENERATOR_SYSTEM

    answer = await _stream_llm(prompt, system, cfg, config)

    sources = [
        {
            "chunk_id": d["chunk_id"],
            "doc_id": d["doc_id"],
            "doc_title": d.get("doc_title") or "",
            "doc_source": d.get("doc_source") or "",
        }
        for d in docs
    ]

    return {
        "answer": answer,
        "source_chunk_ids": [d["chunk_id"] for d in docs],
        "sources": sources,
        "messages": [{"role": "assistant", "content": answer}],
    }


# ---------------------------------------------------------------------------
# Clarify — fires when grading exhausted without finding relevant docs
# ---------------------------------------------------------------------------

async def clarify_node(state: AgentState, config: RunnableConfig) -> dict:
    query = state["messages"][-1]["content"]
    cfg = state.get("llm_config", {})
    system = (
        "You are a helpful assistant. The user asked a question that isn't covered "
        "by the available knowledge base. Politely let them know you don't have that "
        "information, and ask a short clarifying question to help narrow down what "
        "they're looking for — perhaps they meant something different, or there's a "
        "related topic in the knowledge base that would help. Keep it brief and friendly."
    )
    answer = await _stream_llm(f"User asked: {query}", system, cfg, config)
    return {
        "answer": answer,
        "source_chunk_ids": [],
        "sources": [],
        "messages": [{"role": "assistant", "content": answer}],
    }
