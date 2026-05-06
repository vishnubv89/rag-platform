"""
LangGraph node functions for the Agentic RAG loop.

Flow: retriever → grader → generator
                         ↘ rewriter → retriever (loop, max grader_max_loops)
"""
import asyncio
import json
import re

from rag_chatbot.llm.client import generate as _generate
from rag_chatbot.retrieval.vector_store import hybrid_search
from rag_chatbot.agent.state import AgentState


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

async def retriever_node(state: AgentState) -> dict:
    docs = await hybrid_search(state["query"])
    return {"retrieved_docs": docs}


# ---------------------------------------------------------------------------
# Grader — single batch LLM call instead of N parallel calls
# ---------------------------------------------------------------------------

_GRADER_SYSTEM = (
    "You are a relevance grader. Given a query and numbered document chunks, "
    "respond with ONLY a JSON array of integer indices (0-based) of the chunks "
    "relevant to the query. No objects, no explanation, just integers. "
    "Examples: [0,2] means chunks 0 and 2 are relevant. [] means none are relevant."
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
        "retrieved_docs": relevant_docs if passed else docs,
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
    "You are a helpful assistant that answers questions using ONLY the provided "
    "document chunks. Cite sources as [chunk_id: X]. If the documents lack "
    "enough information, say so honestly."
)


async def generator_node(state: AgentState) -> dict:
    query = state["messages"][-1]["content"]
    docs = state["retrieved_docs"]
    cfg = state.get("llm_config", {})

    if docs:
        context = "\n\n".join(f"[chunk_id: {d['chunk_id']}]\n{d['text']}" for d in docs)
        prompt = f"Question: {query}\n\nContext:\n{context}"
    else:
        prompt = f"Question: {query}\n\n(No documents retrieved — answer from general knowledge.)"

    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(
        None, lambda: _generate(prompt, _GENERATOR_SYSTEM, cfg)
    )

    return {
        "answer": answer,
        "source_chunk_ids": [d["chunk_id"] for d in docs],
        "messages": [{"role": "assistant", "content": answer}],
    }
