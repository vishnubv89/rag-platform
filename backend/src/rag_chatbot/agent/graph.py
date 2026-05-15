from langgraph.graph import StateGraph, END

from rag_chatbot.agent.state import AgentState
from rag_chatbot.agent.nodes import (
    contextualize_node,
    intent_node,
    retriever_node,
    grader_node,
    rewriter_node,
    generator_node,
    clarify_node,
    kb_overview_node,
)
from rag_chatbot.config import settings


def _route_after_intent(state: AgentState) -> str:
    if state.get("kb_overview"):
        return "kb_overview"
    return "generate" if state.get("skip_retrieval") else "retrieve"


def _route_after_grader(state: AgentState) -> str:
    if state["grading_passed"]:
        return "generate"
    if state["loop_count"] < settings.grader_max_loops:
        return "rewrite"
    return "clarify"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("contextualize", contextualize_node)
    graph.add_node("intent", intent_node)
    graph.add_node("kb_overview", kb_overview_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("grader", grader_node)
    graph.add_node("rewriter", rewriter_node)
    graph.add_node("generator", generator_node)
    graph.add_node("clarify", clarify_node)

    graph.set_entry_point("contextualize")
    graph.add_edge("contextualize", "intent")

    graph.add_conditional_edges(
        "intent",
        _route_after_intent,
        {"kb_overview": "kb_overview", "generate": "generator", "retrieve": "retriever"},
    )
    graph.add_edge("kb_overview", END)
    graph.add_edge("retriever", "grader")
    graph.add_conditional_edges(
        "grader",
        _route_after_grader,
        {"generate": "generator", "rewrite": "rewriter", "clarify": "clarify"},
    )
    graph.add_edge("rewriter", "retriever")
    graph.add_edge("generator", END)
    graph.add_edge("clarify", END)

    return graph.compile()


rag_graph = build_graph()
