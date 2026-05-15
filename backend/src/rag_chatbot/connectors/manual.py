"""
Manual / Bulk Upload connector.

Config keys: none (upload is handled by the API directly).
This connector acts as the "source" for documents ingested via the UI/API.
list_documents and fetch_document are no-ops — sync is always push-only.
"""
import hashlib
from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register


@register
class ManualConnector(BaseConnector):
    connector_type = "manual"

    async def validate_config(self) -> tuple[bool, str]:
        return True, ""

    async def list_documents(self) -> list[RemoteDocument]:
        # Manual connector is push-only — no remote listing
        return []

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        raise NotImplementedError("Manual connector is push-only")
