from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    # Conversation history: list of {"role": "user"|"assistant", "content": str}
    messages: Annotated[list[dict], operator.add]

    # The most recent user query (may be rewritten)
    query: str

    # Chunks returned by the retriever
    retrieved_docs: list[dict]

    # True when grader accepts the retrieved docs
    grading_passed: bool

    # Number of retrieve-grade loops executed
    loop_count: int

    # Final answer from the generator
    answer: str

    # Source chunk IDs included in the answer
    source_chunk_ids: list[int]

    # Enriched source metadata for citations [{chunk_id, doc_id, doc_title, doc_source}]
    sources: list[dict]

    # True when the query is a greeting/chitchat — skip retrieval
    skip_retrieval: bool

    # Runtime LLM config from app_config table (overrides env defaults)
    llm_config: dict

    # Org that owns this session — retrieval is scoped to this org
    org_id: int | None
