"""
Workday connector.

Config keys:
  base_url       — e.g. https://acme.myworkday.com
  tenant         — Workday tenant name
  client_id      — API client ID
  client_secret  — API client secret
  token_url      — OAuth2 token endpoint

Indexes Workday Knowledge Articles and Job Postings as KB documents.
connector_type = "workday"
"""
import re

import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@register
class WorkdayConnector(BaseConnector):
    connector_type = "workday"

    async def _get_token(self) -> str:
        token_url = self.config["token_url"]
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config["client_id"],
                    "client_secret": self.config["client_secret"],
                },
            )
            r.raise_for_status()
            return r.json()["access_token"]

    def _api_base(self) -> str:
        base = self.config["base_url"].rstrip("/")
        tenant = self.config["tenant"]
        return f"{base}/{tenant}"

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def validate_config(self) -> tuple[bool, str]:
        required = ["base_url", "tenant", "client_id", "client_secret", "token_url"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            await self._get_token()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        token = await self._get_token()
        api_base = self._api_base()
        results: list[RemoteDocument] = []

        async with httpx.AsyncClient(timeout=30) as client:
            headers = self._headers(token)

            # Knowledge articles
            try:
                r = await client.get(
                    f"{api_base}/knowledge/v1/articles",
                    headers=headers,
                    params={"limit": 100},
                )
                if r.status_code == 200:
                    for article in r.json().get("data", []):
                        results.append(RemoteDocument(
                            external_id=f"article:{article['id']}",
                            title=article.get("title", article["id"]),
                            source_url=f"{api_base}/knowledge/v1/articles/{article['id']}",
                            updated_at=article.get("lastUpdated", ""),
                        ))
            except Exception:
                pass

            # Job postings
            try:
                r = await client.get(
                    f"{api_base}/staffing/v6/jobPostings",
                    headers=headers,
                    params={"limit": 100},
                )
                if r.status_code == 200:
                    for posting in r.json().get("data", []):
                        results.append(RemoteDocument(
                            external_id=f"job:{posting['id']}",
                            title=posting.get("jobPostingTitle", posting["id"]),
                            source_url=f"{api_base}/staffing/v6/jobPostings/{posting['id']}",
                            updated_at=posting.get("postedDate", ""),
                        ))
            except Exception:
                pass

        return results

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        token = await self._get_token()
        api_base = self._api_base()
        kind, doc_id = external_id.split(":", 1)

        async with httpx.AsyncClient(timeout=30) as client:
            headers = self._headers(token)
            if kind == "article":
                r = await client.get(
                    f"{api_base}/knowledge/v1/articles/{doc_id}",
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
                title = data.get("title", doc_id)
                raw_text = data.get("content", data.get("body", ""))
                text = _strip_html(raw_text) if raw_text else ""
                updated_at = data.get("lastUpdated", "")
            else:
                r = await client.get(
                    f"{api_base}/staffing/v6/jobPostings/{doc_id}",
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
                title = data.get("jobPostingTitle", doc_id)
                raw_text = data.get("jobDescription", "")
                text = _strip_html(raw_text) if raw_text else ""
                updated_at = data.get("postedDate", "")

        return ConnectorDocument(
            external_id=external_id,
            title=title,
            text=text,
            source_url=f"{api_base}/{'knowledge/v1/articles' if kind == 'article' else 'staffing/v6/jobPostings'}/{doc_id}",
            metadata={"kind": kind, "updated_at": updated_at, "source": "workday"},
        )
