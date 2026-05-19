"""
Slack connector.

Config keys:
  bot_token     — Slack Bot User OAuth Token (xoxb-...)
  channel_ids   — comma-separated channel IDs to index (optional; all public if empty)
  max_messages  — max messages per channel to index (default 500)

Indexes channels and their messages as documents.
Each message thread (parent + replies) becomes one ConnectorDocument.
connector_type = "slack"
"""
import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register


@register
class SlackConnector(BaseConnector):
    connector_type = "slack"

    def _token(self) -> str:
        return self.config["bot_token"]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=30,
        )

    async def validate_config(self) -> tuple[bool, str]:
        if not self.config.get("bot_token"):
            return False, "Missing config key: bot_token"
        try:
            async with self._client() as client:
                r = await client.get("/auth.test")
                r.raise_for_status()
                data = r.json()
                if not data.get("ok"):
                    return False, data.get("error", "auth.test failed")
            return True, ""
        except Exception as e:
            return False, str(e)

    async def _list_channels(self, client: httpx.AsyncClient) -> list[dict]:
        """Return all public channels (or the configured subset)."""
        configured = [
            c.strip()
            for c in self.config.get("channel_ids", "").split(",")
            if c.strip()
        ]

        if configured:
            channels = []
            for ch_id in configured:
                r = await client.get("/conversations.info", params={"channel": ch_id})
                if r.status_code == 200:
                    data = r.json()
                    if data.get("ok"):
                        channels.append(data["channel"])
            return channels

        channels = []
        cursor = ""
        while True:
            params: dict = {"types": "public_channel", "limit": 200, "exclude_archived": "true"}
            if cursor:
                params["cursor"] = cursor
            r = await client.get("/conversations.list", params=params)
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                break
            channels.extend(data.get("channels", []))
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
        return channels

    async def list_documents(self) -> list[RemoteDocument]:
        max_messages = int(self.config.get("max_messages", 500))
        results: list[RemoteDocument] = []

        async with self._client() as client:
            channels = await self._list_channels(client)
            for channel in channels:
                ch_id = channel["id"]
                ch_name = channel.get("name", ch_id)
                fetched = 0
                cursor = ""
                while fetched < max_messages:
                    params: dict = {"channel": ch_id, "limit": min(100, max_messages - fetched)}
                    if cursor:
                        params["cursor"] = cursor
                    r = await client.get("/conversations.history", params=params)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    if not data.get("ok"):
                        break
                    for msg in data.get("messages", []):
                        if msg.get("type") != "message" or msg.get("subtype"):
                            continue
                        ts = msg["ts"]
                        results.append(RemoteDocument(
                            external_id=f"{ch_id}:{ts}",
                            title=f"#{ch_name} — {ts}",
                            source_url=f"https://slack.com/app_redirect?channel={ch_id}&message_ts={ts}",
                            updated_at=ts,
                        ))
                        fetched += 1
                    cursor = data.get("response_metadata", {}).get("next_cursor", "")
                    if not cursor or not data.get("has_more"):
                        break

        return results

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        ch_id, ts = external_id.split(":", 1)

        async with self._client() as client:
            # Get channel name
            r_info = await client.get("/conversations.info", params={"channel": ch_id})
            ch_name = ch_id
            if r_info.status_code == 200:
                data_info = r_info.json()
                if data_info.get("ok"):
                    ch_name = data_info["channel"].get("name", ch_id)

            # Get thread replies
            r_thread = await client.get(
                "/conversations.replies",
                params={"channel": ch_id, "ts": ts},
            )
            messages = []
            if r_thread.status_code == 200:
                data_thread = r_thread.json()
                if data_thread.get("ok"):
                    messages = data_thread.get("messages", [])

        lines = [f"Channel: #{ch_name}"]
        for i, msg in enumerate(messages):
            user = msg.get("user", "unknown")
            text = msg.get("text", "")
            if i == 0:
                lines.append(f"[{user}]: {text}")
            else:
                lines.append(f"  [{user}]: {text}")

        full_text = "\n".join(lines)

        return ConnectorDocument(
            external_id=external_id,
            title=f"#{ch_name} — {ts}",
            text=full_text,
            source_url=f"https://slack.com/app_redirect?channel={ch_id}&message_ts={ts}",
            metadata={"channel_id": ch_id, "ts": ts, "source": "slack"},
        )
