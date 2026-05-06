"""
LangGraph node functions for the Agentic RAG loop.

Flow:
  router → retriever → grader → generator (pass)
                              ↘ rewriter → retriever (loop, max 3x)
"""
import asyncio

from rag_chatbot.llm.client import generate as _generate
from rag_chatbot.retrieval.vector_store import hybrid_search
from rag_chatbot.agent.state import AgentState


# ---------------------------------------------------------------------------
# Router: decide if retrieval is needed
# ---------------------------------------------------------------------------

_ROUTER_SYSTEM = """You are a routing assistant. Decide whether the user question requires
searching a knowledge base (retrieval) or can be answered from general knowledge.

Respond with ONLY one word: RETRIEVE or ANSWER."""


async def router_node(state: AgentState) -> dict:
    query = state["messages"][-1]["content"]
    cfg = state.get("llm_config", {})
    loop = asyncio.get_event_loop()
    decision = await loop.run_in_executor(
        None, lambda: _generate(f"Question: {query}", _ROUTER_SYSTEM, cfg)
    )
    needs_retrieval = "RETRIEVE" in decision.upper()
    return {
        "query": query,
        "grading_passed": False,
        "loop_count": 0,
        "retrieved_docs": [],
        "answer": "",
        "source_chunk_ids": [],
        "_route": "retrieve" if needs_retrieval else "answer",
    }


# ---------------------------------------------------------------------------
# Retriever: call hybrid search
# ---------------------------------------------------------------------------

async def retriever_node(state: AgentState) -> dict:
    docs = await hybrid_search(state["query"])
    return {"retrieved_docs": docs}


# ---------------------------------------------------------------------------
# Grader: score each retrieved doc for relevance
# ---------------------------------------------------------------------------

_GRADER_SYSTEM = """You are a relevance grader. Given a user query and a document chunk,
decide if the chunk is relevant to answering the query.
Respond with ONLY one word: RELEVANT or IRRELEVANT."""


async def grader_node(state: AgentState) -> dict:
    query = state["query"]
    docs = state["retrieved_docs"]
    cfg = state.get("llm_config", {})

    async def grade_doc(doc: dict) -> bool:
        loop = asyncio.get_event_loop()
        prompt = f"Query: {query}\n\nDocument chunk:\n{doc['text']}"
        verdict = await loop.run_in_executor(
            None, lambda: _generate(prompt, _GRADER_SYSTEM, cfg)
        )
        return "RELEVANT" in verdict.upper()

    results = await asyncio.gather(*[grade_doc(d) for d in docs])
    relevant_docs = [doc for doc, ok in zip(docs, results) if ok]
    passed = len(relevant_docs) > 0

    return {
        "retrieved_docs": relevant_docs if passed else docs,
        "grading_passed": passed,
        "loop_count": state["loop_count"] + 1,
    }


# ---------------------------------------------------------------------------
# Rewriter: reformulate the query for a better retrieval
# ---------------------------------------------------------------------------

_REWRITER_SYSTEM = """You are a query rewriting assistant. The initial query failed to
retrieve useful documents. Rewrite the query to be more specific or use different
keywords. Respond with ONLY the rewritten query, nothing else."""


async def rewriter_node(state: AgentState) -> dict:
    cfg = state.get("llm_config", {})
    loop = asyncio.get_event_loop()
    prompt = f"Original query: {state['query']}"
    new_query = await loop.run_in_executor(
        None, lambda: _generate(prompt, _REWRITER_SYSTEM, cfg)
    )
    return {"query": new_query}


# ---------------------------------------------------------------------------
# Generator: synthesize final answer with citations
# ---------------------------------------------------------------------------

_GENERATOR_SYSTEM = """You are a helpful assistant that answers questions using ONLY
the provided document chunks. Always cite sources by referencing [chunk_id: X].
If the documents don't contain enough information, say so honestly."""


async def generator_node(state: AgentState) -> dict:
    query = state["messages"][-1]["content"]
    docs = state["retrieved_docs"]
    cfg = state.get("llm_config", {})

    if docs:
        context = "\n\n".join(
            f"[chunk_id: {d['chunk_id']}]\n{d['text']}" for d in docs
        )
        prompt = f"Question: {query}\n\nContext documents:\n{context}"
    else:
        prompt = f"Question: {query}\n\n(No documents were retrieved — answer from general knowledge.)"

    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(
        None, lambda: _generate(prompt, _GENERATOR_SYSTEM, cfg)
    )

    source_ids = [d["chunk_id"] for d in docs]
    assistant_message = {"role": "assistant", "content": answer}

    return {
        "answer": answer,
        "source_chunk_ids": source_ids,
        "messages": [assistant_message],
    }
