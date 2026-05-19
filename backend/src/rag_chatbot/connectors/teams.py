"""
Microsoft Teams connector.

Config keys:
  tenant_id      — Azure AD tenant ID
  client_id      — App registration client ID
  client_secret  — App registration client secret
  team_id        — Teams team ID to index
  channel_ids    — comma-separated channel IDs (optional; all if empty)

Indexes Teams channels/messages as documents.
connector_type = "teams"
"""
import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@register
class TeamsConnector(BaseConnector):
    connector_type = "teams"

    async def _get_token(self) -> str:
        tenant_id = self.config["tenant_id"]
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config["client_id"],
                    "client_secret": self.config["client_secret"],
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            r.raise_for_status()
            return r.json()["access_token"]

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def validate_config(self) -> tuple[bool, str]:
        required = ["tenant_id", "client_id", "client_secret", "team_id"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            token = await self._get_token()
            team_id = self.config["team_id"]
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{_GRAPH_BASE}/teams/{team_id}",
                    headers=self._headers(token),
                )
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def _list_channels(self, client: httpx.AsyncClient, token: str) -> list[dict]:
        team_id = self.config["team_id"]
        configured = [
            c.strip()
            for c in self.config.get("channel_ids", "").split(",")
            if c.strip()
        ]
        r = await client.get(
            f"{_GRAPH_BASE}/teams/{team_id}/channels",
            headers=self._headers(token),
        )
        r.raise_for_status()
        channels = r.json().get("value", [])
        if configured:
            channels = [c for c in channels if c["id"] in configured]
        return channels

    async def list_documents(self) -> list[RemoteDocument]:
        token = await self._get_token()
        team_id = self.config["team_id"]
        results: list[RemoteDocument] = []

        async with httpx.AsyncClient(timeout=30) as client:
            channels = await self._list_channels(client, token)
            for channel in channels:
                ch_id = channel["id"]
                ch_name = channel.get("displayName", ch_id)
                r = await client.get(
                    f"{_GRAPH_BASE}/teams/{team_id}/channels/{ch_id}/messages",
                    headers=self._headers(token),
                    params={"$top": 50},
                )
                if r.status_code != 200:
                    continue
                for msg in r.json().get("value", []):
                    msg_id = msg["id"]
                    created = msg.get("createdDateTime", "")
                    results.append(RemoteDocument(
                        external_id=f"{team_id}:{ch_id}:{msg_id}",
                        title=f"{ch_name} — {msg_id}",
                        source_url=msg.get("webUrl", ""),
                        updated_at=created,
                    ))

        return results

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        team_id, ch_id, msg_id = external_id.split(":", 2)
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch the parent message
            r_msg = await client.get(
                f"{_GRAPH_BASE}/teams/{team_id}/channels/{ch_id}/messages/{msg_id}",
                headers=self._headers(token),
            )
            r_msg.raise_for_status()
            parent = r_msg.json()

            # Fetch replies
            r_replies = await client.get(
                f"{_GRAPH_BASE}/teams/{team_id}/channels/{ch_id}/messages/{msg_id}/replies",
                headers=self._headers(token),
            )
            replies = r_replies.json().get("value", []) if r_replies.status_code == 200 else []

            # Channel name
            r_ch = await client.get(
                f"{_GRAPH_BASE}/teams/{team_id}/channels/{ch_id}",
                headers=self._headers(token),
            )
            ch_name = ch_id
            if r_ch.status_code == 200:
                ch_name = r_ch.json().get("displayName", ch_id)

        def _msg_text(msg: dict) -> str:
            body = msg.get("body", {})
            return body.get("content", "").strip()

        sender = parent.get("from", {}).get("user", {}).get("displayName", "unknown")
        lines = [f"Channel: {ch_name}", f"[{sender}]: {_msg_text(parent)}"]
        for reply in replies:
            r_sender = reply.get("from", {}).get("user", {}).get("displayName", "unknown")
            lines.append(f"  [{r_sender}]: {_msg_text(reply)}")

        return ConnectorDocument(
            external_id=external_id,
            title=f"{ch_name} — {msg_id}",
            text="\n".join(lines),
            source_url=parent.get("webUrl", ""),
            metadata={"team_id": team_id, "channel_id": ch_id, "message_id": msg_id, "source": "teams"},
        )
