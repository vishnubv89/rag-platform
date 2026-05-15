"""
Zendesk connector.

Syncs Help Center articles from a Zendesk Guide instance.
Optionally also syncs resolved ticket conversations.

Config keys:
  subdomain      e.g. "acme" for acme.zendesk.com  (required)
  email          Zendesk agent email  (required)
  api_token      Zendesk API token (Admin Center → Apps → API)  (required)
  locale         (optional) article locale, e.g. "en-us". Defaults to all.
  sync_tickets   (optional) "true" to also sync resolved ticket threads.
                 Defaults to "false". Requires the agent to have ticket access.
  ticket_limit   (optional) max resolved tickets to sync. Defaults to 500.

Setup:
  1. In Zendesk Admin Center → Apps and Integrations → APIs → Zendesk API:
     - Enable Token Access
     - Create an API Token
  2. Use the agent email + that token in the config above.
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
class ZendeskConnector(BaseConnector):
    connector_type = "zendesk"

    def _base(self) -> str:
        return f"https://{self.config['subdomain']}.zendesk.com"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base(),
            auth=(f"{self.config['email']}/token", self.config["api_token"]),
            timeout=30,
        )

    def _sync_tickets(self) -> bool:
        return str(self.config.get("sync_tickets", "false")).lower() == "true"

    def _ticket_limit(self) -> int:
        try:
            return int(self.config.get("ticket_limit", 500))
        except (ValueError, TypeError):
            return 500

    async def validate_config(self) -> tuple[bool, str]:
        required = ["subdomain", "email", "api_token"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            async with self._client() as client:
                r = await client.get("/api/v2/help_center/articles.json", params={"per_page": 1})
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    # ── Articles ─────────────────────────────────────────────────────────────

    async def _list_articles(self) -> list[RemoteDocument]:
        results: list[RemoteDocument] = []
        locale = self.config.get("locale", "")
        path = (
            f"/api/v2/help_center/{locale}/articles.json"
            if locale
            else "/api/v2/help_center/articles.json"
        )

        async with self._client() as client:
            url: str | None = path
            while url:
                r = await client.get(url, params={"per_page": 100, "sort_by": "updated_at", "sort_order": "desc"})
                r.raise_for_status()
                data = r.json()
                for article in data.get("articles", []):
                    if not article.get("draft", False):
                        results.append(RemoteDocument(
                            external_id=f"article:{article['id']}",
                            title=article.get("title", str(article["id"])),
                            source_url=article.get("html_url", ""),
                            updated_at=article.get("updated_at", ""),
                        ))
                next_page = data.get("next_page")
                url = next_page if next_page and not next_page.endswith("page=1") else None

        return results

    async def _fetch_article(self, article_id: str) -> ConnectorDocument:
        async with self._client() as client:
            r = await client.get(f"/api/v2/help_center/articles/{article_id}.json")
            r.raise_for_status()
            article = r.json()["article"]

        body_html = article.get("body", "")
        text = _strip_html(body_html)
        text = re.sub(r"\x00", "", text)

        return ConnectorDocument(
            external_id=f"article:{article_id}",
            title=article.get("title", article_id),
            text=text,
            source_url=article.get("html_url", ""),
            metadata={
                "updated_at": article.get("updated_at", ""),
                "section_id": article.get("section_id"),
                "locale": article.get("locale", ""),
                "source": "zendesk",
                "kind": "article",
            },
        )

    # ── Tickets ───────────────────────────────────────────────────────────────

    async def _list_tickets(self) -> list[RemoteDocument]:
        results: list[RemoteDocument] = []
        limit = self._ticket_limit()
        fetched = 0

        async with self._client() as client:
            # Search for solved/closed tickets
            url: str | None = "/api/v2/search.json"
            params: dict = {
                "query": "type:ticket status:solved",
                "sort_by": "updated_at",
                "sort_order": "desc",
                "per_page": min(100, limit),
            }
            while url and fetched < limit:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                for ticket in data.get("results", []):
                    if ticket.get("result_type") != "ticket":
                        continue
                    results.append(RemoteDocument(
                        external_id=f"ticket:{ticket['id']}",
                        title=f"[Ticket #{ticket['id']}] {ticket.get('subject', '')}",
                        source_url=f"{self._base()}/agent/tickets/{ticket['id']}",
                        updated_at=ticket.get("updated_at", ""),
                    ))
                    fetched += 1
                    if fetched >= limit:
                        break
                next_page = data.get("next_page")
                url = next_page if next_page else None
                params = {}  # next_page URL already has params

        return results

    async def _fetch_ticket(self, ticket_id: str) -> ConnectorDocument:
        async with self._client() as client:
            t_r = await client.get(f"/api/v2/tickets/{ticket_id}.json")
            t_r.raise_for_status()
            ticket = t_r.json()["ticket"]

            c_r = await client.get(
                f"/api/v2/tickets/{ticket_id}/comments.json",
                params={"per_page": 100},
            )
            c_r.raise_for_status()
            comments = c_r.json().get("comments", [])

        lines = [f"Subject: {ticket.get('subject', '')}"]
        for c in comments:
            body = _strip_html(c.get("html_body") or c.get("body", ""))
            if body.strip():
                lines.append(f"---\n{body}")

        text = re.sub(r"\x00", "", "\n".join(lines))
        return ConnectorDocument(
            external_id=f"ticket:{ticket_id}",
            title=f"[Ticket #{ticket_id}] {ticket.get('subject', '')}",
            text=text,
            source_url=f"{self._base()}/agent/tickets/{ticket_id}",
            metadata={
                "updated_at": ticket.get("updated_at", ""),
                "status": ticket.get("status", ""),
                "tags": ticket.get("tags", []),
                "source": "zendesk",
                "kind": "ticket",
            },
        )

    # ── BaseConnector interface ───────────────────────────────────────────────

    async def list_documents(self) -> list[RemoteDocument]:
        docs = await self._list_articles()
        if self._sync_tickets():
            docs += await self._list_tickets()
        return docs

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        kind, doc_id = external_id.split(":", 1)
        if kind == "article":
            return await self._fetch_article(doc_id)
        elif kind == "ticket":
            return await self._fetch_ticket(doc_id)
        raise ValueError(f"Unknown Zendesk external_id format: {external_id!r}")
