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

    def _base_query(self) -> str:
        q = "workflow_state=published"
        if self.config.get("kb_sys_id"):
            q += f"^kb_knowledge_base={self.config['kb_sys_id']}"
        if self.config.get("category"):
            q += f"^kb_category={self.config['category']}"
        return q

    async def validate_config(self) -> tuple[bool, str]:
        required = ["instance_url", "username", "password"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            async with self._client() as client:
                r = await client.get(
                    "/api/now/table/kb_knowledge",
                    params={"sysparm_limit": 1, "sysparm_query": self._base_query()},
                )
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        PAGE = 200
        docs: list[RemoteDocument] = []
        base_params = {
            "sysparm_fields": "sys_id,short_description,sys_updated_on",
            "sysparm_query": self._base_query(),
            "sysparm_limit": PAGE,
        }
        async with self._client() as client:
            offset = 0
            while True:
                r = await client.get(
                    "/api/now/table/kb_knowledge",
                    params={**base_params, "sysparm_offset": offset},
                )
                r.raise_for_status()
                result = r.json().get("result", [])
                # ServiceNow returns a dict (not a list) when exactly one record matches
                page = [result] if isinstance(result, dict) else result
                for item in page:
                    docs.append(RemoteDocument(
                        external_id=item["sys_id"],
                        title=item.get("short_description", "Untitled"),
                        source_url=f"{self.config['instance_url'].rstrip('/')}/kb_view.do?sys_kb_id={item['sys_id']}",
                        updated_at=item.get("sys_updated_on", ""),
                    ))
                if len(page) < PAGE:
                    break
                offset += PAGE
        return docs

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        async with self._client() as client:
            r = await client.get(
                f"/api/now/table/kb_knowledge/{external_id}",
                params={"sysparm_fields": "sys_id,short_description,text,sys_updated_on"},
            )
            r.raise_for_status()
            result = r.json()["result"]
            # Single-record endpoint always returns a dict, but normalise defensively
            item = result[0] if isinstance(result, list) else result

        text = _strip_html(item.get("text") or "")
        return ConnectorDocument(
            external_id=item["sys_id"],
            title=item.get("short_description", "Untitled"),
            text=text,
            source_url=f"{self.config['instance_url'].rstrip('/')}/kb_view.do?sys_kb_id={item['sys_id']}",
            metadata={"updated_at": item.get("sys_updated_on", ""), "source": "servicenow"},
        )
