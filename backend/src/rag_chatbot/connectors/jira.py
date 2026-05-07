"""
Jira connector (Cloud & Server/Data Center).

Syncs Jira issues (summary + description + comments) and optionally
Confluence-style Jira pages (Jira Work Management / Service Management).

Config keys:
  base_url      e.g. "https://acme.atlassian.net" (Cloud) or
                "https://jira.acme.com" (Server/DC)  (required)
  email         Atlassian account email (Cloud) or username (Server)  (required)
  api_token     Atlassian API token (Cloud) or password (Server)  (required)
  jql           (optional) JQL filter. Defaults to all non-archived issues:
                "project is not EMPTY ORDER BY updated DESC"
  max_issues    (optional) cap on issues to sync. Defaults to 2000.
  cloud         (optional) "true" (default) | "false" for Server/DC

Setup:
  Cloud:
    1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
    2. Create an API token
    3. Use your Atlassian email + that token
  Server/DC:
    1. Use your Jira username + password (or a personal access token)
    2. Set cloud=false
"""
import re

import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register


def _strip_jira_markup(text: str) -> str:
    """Remove Jira wiki markup, ADF JSON artifacts, and HTML."""
    # Remove Jira wiki markup bold/italic
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    # Remove Jira colour macros
    text = re.sub(r"\{[^}]+\}", "", text)
    # Remove basic HTML
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _adf_to_text(node: dict | list | str | None) -> str:
    """Recursively extract plain text from Atlassian Document Format (ADF) JSON."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(_adf_to_text(n) for n in node)
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = []
        for child in node.get("content", []):
            parts.append(_adf_to_text(child))
        return " ".join(parts)
    return ""


def _render_description(description) -> str:
    """Handle both legacy wiki markup (str) and ADF (dict)."""
    if description is None:
        return ""
    if isinstance(description, str):
        return _strip_jira_markup(description)
    if isinstance(description, dict):
        return _strip_jira_markup(_adf_to_text(description))
    return ""


@register
class JiraConnector(BaseConnector):
    connector_type = "jira"

    def _is_cloud(self) -> bool:
        return str(self.config.get("cloud", "true")).lower() != "false"

    def _base(self) -> str:
        return self.config["base_url"].rstrip("/")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base(),
            auth=(self.config["email"], self.config["api_token"]),
            headers={"Accept": "application/json"},
            timeout=30,
        )

    def _api(self, path: str) -> str:
        return f"/rest/api/3/{path.lstrip('/')}"

    def _jql(self) -> str:
        return self.config.get("jql", "project is not EMPTY ORDER BY updated DESC")

    def _max_issues(self) -> int:
        try:
            return int(self.config.get("max_issues", 2000))
        except (ValueError, TypeError):
            return 2000

    async def validate_config(self) -> tuple[bool, str]:
        required = ["base_url", "email", "api_token"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            async with self._client() as client:
                r = await client.get(self._api("myself"))
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        results: list[RemoteDocument] = []
        max_issues = self._max_issues()
        start_at = 0
        page_size = 100

        async with self._client() as client:
            while len(results) < max_issues:
                r = await client.get(
                    self._api("search"),
                    params={
                        "jql": self._jql(),
                        "startAt": start_at,
                        "maxResults": min(page_size, max_issues - len(results)),
                        "fields": "summary,updated",
                    },
                )
                r.raise_for_status()
                data = r.json()
                issues = data.get("issues", [])
                if not issues:
                    break

                for issue in issues:
                    fields = issue.get("fields", {})
                    base = self._base()
                    results.append(RemoteDocument(
                        external_id=issue["key"],
                        title=f"[{issue['key']}] {fields.get('summary', '')}",
                        source_url=f"{base}/browse/{issue['key']}",
                        updated_at=fields.get("updated", ""),
                    ))

                start_at += len(issues)
                if start_at >= data.get("total", 0):
                    break

        return results

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        async with self._client() as client:
            r = await client.get(
                self._api(f"issue/{external_id}"),
                params={"fields": "summary,description,comment,status,priority,labels,updated,issuetype"},
            )
            r.raise_for_status()
            issue = r.json()

        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        description = _render_description(fields.get("description"))

        # Flatten comments
        comment_lines: list[str] = []
        comments = fields.get("comment", {}).get("comments", [])
        for c in comments:
            body = _render_description(c.get("body"))
            author = c.get("author", {}).get("displayName", "unknown")
            if body.strip():
                comment_lines.append(f"[{author}]: {body}")

        parts = [f"Issue: {external_id}\nSummary: {summary}"]
        if description:
            parts.append(f"Description:\n{description}")
        if comment_lines:
            parts.append("Comments:\n" + "\n".join(comment_lines))

        text = re.sub(r"\x00", "", "\n\n".join(parts))

        return ConnectorDocument(
            external_id=external_id,
            title=f"[{external_id}] {summary}",
            text=text,
            source_url=f"{self._base()}/browse/{external_id}",
            metadata={
                "updated_at": fields.get("updated", ""),
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "labels": fields.get("labels", []),
                "issue_type": fields.get("issuetype", {}).get("name", ""),
                "source": "jira",
            },
        )
