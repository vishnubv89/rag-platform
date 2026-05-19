"""
Action registry — maps action_type strings to async callables.

An action callable receives (params: dict, state: AgentState) and returns
ActionResult(success, message, data).
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from rag_chatbot.agent.state import AgentState  # forward-ref OK


@dataclass
class ActionResult:
    success: bool
    message: str                    # human-readable outcome
    data: dict = field(default_factory=dict)  # structured response (ticket ID, link, etc.)


ActionFn = Callable[..., Coroutine[Any, Any, ActionResult]]

_REGISTRY: dict[str, ActionFn] = {}


def register_action(name: str):
    def decorator(fn: ActionFn) -> ActionFn:
        _REGISTRY[name] = fn
        return fn
    return decorator


async def dispatch(action_type: str, params: dict, state: "AgentState") -> ActionResult:
    fn = _REGISTRY.get(action_type)
    if fn is None:
        return ActionResult(success=False, message=f"Unknown action: {action_type}")
    return await fn(params, state)


def available_actions() -> list[str]:
    return list(_REGISTRY)
