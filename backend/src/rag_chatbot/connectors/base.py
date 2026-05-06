"""
Connector protocol — every source connector implements BaseConnector.

A connector is responsible for:
  1. Validating its config (credentials, URLs)
  2. Listing documents available in the source (id + hash for change detection)
  3. Fetching the full text of a single document
  4. Running an incremental sync (list → diff → fetch changed → embed → upsert)
"""
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class RemoteDocument:
    """Lightweight listing entry — returned by list_documents()."""
    external_id: str        # stable ID in the source system
    title: str
    source_url: str
    updated_at: str         # ISO-8601 string; used for ordering, not hashing
    content_hash: str = ""  # SHA-256 of content; computed by fetch if not provided


@dataclass
class ConnectorDocument:
    """Full document — returned by fetch_document()."""
    external_id: str
    title: str
    text: str
    source_url: str
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


class BaseConnector(ABC):
    connector_type: str = "base"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def validate_config(self) -> tuple[bool, str]:
        """Return (ok, error_message). error_message is '' on success."""

    @abstractmethod
    async def list_documents(self) -> list[RemoteDocument]:
        """Return all documents available in the source."""

    @abstractmethod
    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        """Fetch and return the full text of a single document."""

    async def iter_changed(
        self,
        existing: dict[str, str],  # {external_id: content_hash}
    ) -> AsyncIterator[ConnectorDocument]:
        """
        Yield documents that are new or whose hash has changed.
        Default implementation: list all, compare hashes, fetch changed.
        Connectors may override for efficiency (e.g. delta API).
        """
        remote = await self.list_documents()
        for entry in remote:
            stored_hash = existing.get(entry.external_id, "")
            doc = await self.fetch_document(entry.external_id)
            if doc.content_hash != stored_hash:
                yield doc

    async def deleted_ids(
        self,
        existing: dict[str, str],  # {external_id: content_hash}
    ) -> list[str]:
        """Return external_ids present locally but gone from the source."""
        remote_ids = {d.external_id for d in await self.list_documents()}
        return [eid for eid in existing if eid not in remote_ids]
