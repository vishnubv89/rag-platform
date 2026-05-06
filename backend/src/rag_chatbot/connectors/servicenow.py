"""
ServiceNow Knowledge Base connector.

Config keys:
  instance_url   e.g. https://acme.service-now.com
  username       ServiceNow username (basic auth)
  password       ServiceNow password or API token
  kb_sys_id      (optional) filter to a specific knowledge base sys_id
  category       (optional) filter by category sys_id
"""
import hashlib
from typing import Any

import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register


def _strip_html(html: str) -> str:
    """Minimal HTML → plain text. Avoids a heavy dependency."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@register
class ServiceNowConnector(BaseConnector):
    connector_type = "servicenow"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.config["instance_url"].rstrip("/"),
            auth=(self.config["username"], self.config["password"]),
            timeout=30,
        )

    def _params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "sysparm_fields": "sys_id,short_description,sys_updated_on,kb_knowledge_base,workflow_state",
            "sysparm_query": "workflow_state=published",
            "sysparm_limit": 1000,
        }
        if self.config.get("kb_sys_id"):
            params["sysparm_query"] += f"^kb_knowledge_base={self.config['kb_sys_id']}"
        if self.config.get("category"):
            params["sysparm_query"] += f"^kb_category={self.config['category']}"
        return params

    async def validate_config(self) -> tuple[bool, str]:
        required = ["instance_url", "username", "password"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            async with self._client() as client:
                r = await client.get(
                    "/api/now/table/kb_knowledge",
                    params={"sysparm_limit": 1},
                )
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        async with self._client() as client:
            r = await client.get("/api/now/table/kb_knowledge", params=self._params())
            r.raise_for_status()
            results = r.json().get("result", [])

        docs = []
        for item in results:
            docs.append(RemoteDocument(
                external_id=item["sys_id"],
                title=item.get("short_description", "Untitled"),
                source_url=f"{self.config['instance_url'].rstrip('/')}/kb_view.do?sys_kb_id={item['sys_id']}",
                updated_at=item.get("sys_updated_on", ""),
            ))
        return docs

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        async with self._client() as client:
            r = await client.get(
                f"/api/now/table/kb_knowledge/{external_id}",
                params={"sysparm_fields": "sys_id,short_description,text,sys_updated_on"},
            )
            r.raise_for_status()
            item = r.json()["result"]

        text = _strip_html(item.get("text") or "")
        return ConnectorDocument(
            external_id=item["sys_id"],
            title=item.get("short_description", "Untitled"),
            text=text,
            source_url=f"{self.config['instance_url'].rstrip('/')}/kb_view.do?sys_kb_id={item['sys_id']}",
            metadata={"updated_at": item.get("sys_updated_on", ""), "source": "servicenow"},
        )
