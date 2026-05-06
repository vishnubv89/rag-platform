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
