"""
Azure AD identity connector.

Config keys:
  tenant_id, client_id, client_secret

Syncs Azure AD group memberships for a user into user_attributes.
connector_type = "azure_ad"
"""
import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register
from rag_chatbot.db.connection import get_pool

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@register
class AzureADConnector(BaseConnector):
    connector_type = "azure_ad"

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
        required = ["tenant_id", "client_id", "client_secret"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            await self._get_token()
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        return []

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        raise NotImplementedError("Azure AD is an identity connector, not a KB source")

    async def sync_user_attributes(self, user_id: str) -> None:
        """Sync Azure AD group memberships and department into user_attributes."""
        token = await self._get_token()
        headers = self._headers(token)

        pool = await get_pool()
        async with httpx.AsyncClient(timeout=30) as client:
            # Transitive group memberships
            r_groups = await client.get(
                f"{_GRAPH_BASE}/users/{user_id}/transitiveMemberOf",
                headers=headers,
            )
            groups: list[dict] = []
            if r_groups.status_code == 200:
                groups = r_groups.json().get("value", [])

            # User profile for department
            r_user = await client.get(
                f"{_GRAPH_BASE}/users/{user_id}",
                headers=headers,
                params={"$select": "department"},
            )
            department = ""
            if r_user.status_code == 200:
                department = r_user.json().get("department") or ""

        async with pool.acquire() as conn:
            async with conn.transaction():
                for group in groups:
                    display_name = group.get("displayName", "")
                    if not display_name:
                        continue
                    await conn.execute(
                        """INSERT INTO user_attributes (user_id, attr_type, attr_value)
                           VALUES ($1, $2, $3)
                           ON CONFLICT (user_id, attr_type, attr_value) DO UPDATE
                           SET synced_at = now()""",
                        user_id, "group", display_name,
                    )
                if department:
                    await conn.execute(
                        """INSERT INTO user_attributes (user_id, attr_type, attr_value)
                           VALUES ($1, $2, $3)
                           ON CONFLICT (user_id, attr_type, attr_value) DO UPDATE
                           SET synced_at = now()""",
                        user_id, "department", department,
                    )
