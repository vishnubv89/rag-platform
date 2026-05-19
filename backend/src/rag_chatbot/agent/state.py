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

    # True when the query is asking for a KB overview/summary — bypass retrieval
    kb_overview: bool

    # Runtime LLM config from app_config table (overrides env defaults)
    llm_config: dict

    # Org that owns this session — retrieval is scoped to this org
    org_id: int | None

    # Raw Zitadel access token for the current user.
    # When set, retriever_node attempts an OBO token exchange with ServiceNow
    # and supplements pgvector results with a live permission-aware SN search.
    # None when the user authenticated via local password login (no Zitadel token).
    user_zitadel_token: str | None

    # Detected action intent (e.g. "servicenow_create_incident") — None = no action
    action_intent: str | None

    # Extracted action parameters from the query (filled by intent_node)
    action_params: dict

    # Result of the action_node execution
    action_result: dict | None
