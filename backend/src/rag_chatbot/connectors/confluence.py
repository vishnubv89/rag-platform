"""
Confluence connector (Cloud & Server).

Config keys:
  base_url    e.g. https://acme.atlassian.net  (Cloud) or https://wiki.acme.com
  username    Atlassian account email (Cloud) or username (Server)
  api_token   Atlassian API token (Cloud) or password (Server)
  space_key   (optional) limit to a specific Confluence space key e.g. KB
  cloud       true | false  (default true — Cloud uses /wiki prefix)
"""
import re

import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register


def _storage_to_text(storage_html: str) -> str:
    """Convert Confluence storage format (XHTML) to plain text."""
    text = re.sub(r"<[^>]+>", " ", storage_html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@register
class ConfluenceConnector(BaseConnector):
    connector_type = "confluence"

    def _base(self) -> str:
        base = self.config["base_url"].rstrip("/")
        is_cloud = str(self.config.get("cloud", "true")).lower() != "false"
        return f"{base}/wiki" if is_cloud else base

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base(),
            auth=(self.config["username"], self.config["api_token"]),
            timeout=30,
        )

    def _content_params(self) -> dict:
        params: dict = {
            "type": "page",
            "status": "current",
            "expand": "version",
            "limit": 250,
        }
        if self.config.get("space_key"):
            params["spaceKey"] = self.config["space_key"]
        return params

    async def validate_config(self) -> tuple[bool, str]:
        required = ["base_url", "username", "api_token"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            async with self._client() as client:
                r = await client.get("/rest/api/content", params={"limit": 1})
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        results = []
        start = 0
        async with self._client() as client:
            while True:
                params = {**self._content_params(), "start": start}
                r = await client.get("/rest/api/content", params=params)
                r.raise_for_status()
                data = r.json()
                for page in data.get("results", []):
                    results.append(RemoteDocument(
                        external_id=page["id"],
                        title=page["title"],
                        source_url=f"{self._base()}/pages/{page['id']}",
                        updated_at=page["version"]["when"],
                    ))
                if data.get("_links", {}).get("next"):
                    start += len(data["results"])
                else:
                    break
        return results

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        async with self._client() as client:
            r = await client.get(
                f"/rest/api/content/{external_id}",
                params={"expand": "body.storage,version,space"},
            )
            r.raise_for_status()
            page = r.json()

        storage = page.get("body", {}).get("storage", {}).get("value", "")
        text = _storage_to_text(storage)
        base_url = self.config["base_url"].rstrip("/")

        return ConnectorDocument(
            external_id=external_id,
            title=page["title"],
            text=text,
            source_url=f"{base_url}/wiki/pages/{external_id}",
            metadata={
                "updated_at": page["version"]["when"],
                "space": page.get("space", {}).get("key", ""),
                "source": "confluence",
            },
        )
