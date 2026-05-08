"""
LangGraph node functions for the Agentic RAG loop.

Flow: intent → retriever → grader → generator
                         ↘ rewriter → retriever (loop, max grader_max_loops)
      intent (greeting)  → generator  (skip retrieval entirely)
"""
import asyncio
import json
import re

from rag_chatbot.llm.client import generate as _generate
from rag_chatbot.retrieval.vector_store import hybrid_search
from rag_chatbot.agent.state import AgentState


# ---------------------------------------------------------------------------
# Intent — lightweight keyword check, no LLM call
# ---------------------------------------------------------------------------

_CHITCHAT_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|howdy|greetings|good\s*(morning|afternoon|evening|day)|"
    r"what'?s\s+up|sup|yo+|hiya|how\s+are\s+you|how\s+do\s+you\s+do|nice\s+to\s+meet\s+you|"
    r"thanks?(\s+you)?|thank\s+you|bye+|goodbye|see\s+you|take\s+care|"
    r"who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do)\W*$",
    re.IGNORECASE,
)


async def intent_node(state: AgentState) -> dict:
    query = state["messages"][-1]["content"]
    return {"skip_retrieval": bool(_CHITCHAT_RE.match(query.strip()))}


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
    "You are a strict relevance grader. Given a query and numbered document chunks, "
    "respond with ONLY a JSON array of integer indices (0-based) of chunks that "
    "DIRECTLY answer the query. Be conservative — if a chunk is only tangentially "
    "related, exclude it. If you have any doubt, exclude it. "
    "A chunk is relevant only if it contains specific information that addresses the query. "
    "Examples: [0,2] means chunks 0 and 2 are relevant. [] means none are relevant. "
    "No objects, no explanation — just the JSON integer array."
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

    doc_list = "\n".join(f"[{i}] {d['text'][:300]}" for i, d in enumerate(docs))
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


async def generator_node(state: AgentState) -> dict:
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

    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(
        None, lambda: _generate(prompt, system, cfg)
    )

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

async def clarify_node(state: AgentState) -> dict:
    query = state["messages"][-1]["content"]
    cfg = state.get("llm_config", {})
    system = (
        "You are a helpful assistant. The user asked a question that isn't covered "
        "by the available knowledge base. Politely let them know you don't have that "
        "information, and ask a short clarifying question to help narrow down what "
        "they're looking for — perhaps they meant something different, or there's a "
        "related topic in the knowledge base that would help. Keep it brief and friendly."
    )
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(
        None, lambda: _generate(f"User asked: {query}", system, cfg)
    )
    return {
        "answer": answer,
        "source_chunk_ids": [],
        "sources": [],
        "messages": [{"role": "assistant", "content": answer}],
    }
