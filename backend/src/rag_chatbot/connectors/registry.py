"""
Connector registry — maps connector_type strings to connector classes.
Import here to register; the sync engine and API use get() to instantiate.
"""
from rag_chatbot.connectors.base import BaseConnector

_REGISTRY: dict[str, type[BaseConnector]] = {}


def register(cls: type[BaseConnector]) -> type[BaseConnector]:
    _REGISTRY[cls.connector_type] = cls
    return cls


def get(connector_type: str, config: dict) -> BaseConnector:
    cls = _REGISTRY.get(connector_type)
    if cls is None:
        raise ValueError(f"Unknown connector type: {connector_type!r}. "
                         f"Available: {list(_REGISTRY)}")
    return cls(config)


def available_types() -> list[str]:
    return list(_REGISTRY)


# Import all connectors to trigger registration
from rag_chatbot.connectors import manual, servicenow, sharepoint, confluence, gdrive, zendesk, jira  # noqa: E402, F401
