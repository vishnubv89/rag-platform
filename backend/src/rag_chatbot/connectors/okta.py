"""
Okta identity connector.

Config keys:
  domain       — e.g. acme.okta.com
  api_token    — Okta API token

Syncs Okta group memberships for a user into user_attributes.
connector_type = "okta"
"""
import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register
from rag_chatbot.db.connection import get_pool


@register
class OktaConnector(BaseConnector):
    connector_type = "okta"

    def _base(self) -> str:
        return f"https://{self.config['domain']}/api/v1"

    def _headers(self) -> dict:
        return {
            "Authorization": f"SSWS {self.config['api_token']}",
            "Accept": "application/json",
        }

    async def validate_config(self) -> tuple[bool, str]:
        required = ["domain", "api_token"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{self._base()}/users/me",
                    headers=self._headers(),
                )
                r.raise_for_status()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        return []

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        raise NotImplementedError("Okta is an identity connector, not a KB source")

    async def sync_user_attributes(self, user_id: str) -> None:
        """Sync Okta group memberships and department into user_attributes."""
        headers = self._headers()
        base = self._base()
        pool = await get_pool()

        async with httpx.AsyncClient(timeout=30) as client:
            # Group memberships
            r_groups = await client.get(
                f"{base}/users/{user_id}/groups",
                headers=headers,
            )
            groups: list[dict] = r_groups.json() if r_groups.status_code == 200 else []

            # User profile
            r_user = await client.get(
                f"{base}/users/{user_id}",
                headers=headers,
            )
            department = ""
            if r_user.status_code == 200:
                profile = r_user.json().get("profile", {})
                department = profile.get("department") or ""

        async with pool.acquire() as conn:
            async with conn.transaction():
                for group in groups:
                    profile = group.get("profile", {})
                    name = profile.get("name", "")
                    if not name:
                        continue
                    await conn.execute(
                        """INSERT INTO user_attributes (user_id, attr_type, attr_value)
                           VALUES ($1, $2, $3)
                           ON CONFLICT (user_id, attr_type, attr_value) DO UPDATE
                           SET synced_at = now()""",
                        user_id, "group", name,
                    )
                if department:
                    await conn.execute(
                        """INSERT INTO user_attributes (user_id, attr_type, attr_value)
                           VALUES ($1, $2, $3)
                           ON CONFLICT (user_id, attr_type, attr_value) DO UPDATE
                           SET synced_at = now()""",
                        user_id, "department", department,
                    )
