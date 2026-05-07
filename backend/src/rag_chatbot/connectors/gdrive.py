"""
Google Drive connector.

Fetches Google Docs, Sheets, and uploaded files (PDF, TXT, MD) from a
Drive folder (or the entire My Drive if no folder is specified).

Config keys:
  service_account_json   JSON string of a GCP service account key with
                         Drive read scope (share target folders with the
                         service account email).  Required.
  folder_id              (optional) Google Drive folder ID to limit sync.
                         If omitted, searches all files the service account
                         can access.
  include_types          (optional) comma-separated MIME types to include.
                         Defaults to Docs, Sheets, PDFs, plain text, Markdown.

Setup:
  1. Create a GCP service account with the Drive API enabled.
  2. Download the JSON key.
  3. Share the target folder(s) with the service account email (Viewer role).
  4. Paste the full JSON key string as service_account_json in connector config.
"""
import io
import json
import re

import httpx

from rag_chatbot.connectors.base import BaseConnector, ConnectorDocument, RemoteDocument
from rag_chatbot.connectors.registry import register

_DRIVE_API = "https://www.googleapis.com/drive/v3"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EXPORT_URL = "https://www.googleapis.com/drive/v3/files/{id}/export"
_DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files/{id}?alt=media"

_DEFAULT_MIME_TYPES = [
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
]

# Export targets for Google Workspace formats
_EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}

_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _service_account_jwt(sa_info: dict) -> str:
    """Build a signed JWT assertion for service account auth."""
    import base64
    import time
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa_info["client_email"],
        "scope": _SCOPE,
        "aud": _TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=")

    signing_input = header + b"." + payload
    private_key = serialization.load_pem_private_key(
        sa_info["private_key"].encode(), password=None
    )
    sig = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
    return (signing_input + b"." + sig_b64).decode()


async def _get_access_token(sa_info: dict) -> str:
    jwt = _service_account_jwt(sa_info)
    async with httpx.AsyncClient() as client:
        r = await client.post(_TOKEN_URL, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt,
        })
        r.raise_for_status()
        return r.json()["access_token"]


@register
class GDriveConnector(BaseConnector):
    connector_type = "gdrive"

    def _sa_info(self) -> dict:
        raw = self.config.get("service_account_json", "")
        if not raw:
            raise ValueError("service_account_json is required")
        return json.loads(raw)

    def _mime_filter(self) -> list[str]:
        raw = self.config.get("include_types", "")
        if raw:
            return [m.strip() for m in raw.split(",") if m.strip()]
        return _DEFAULT_MIME_TYPES

    async def _client_with_token(self) -> tuple[httpx.AsyncClient, str]:
        token = await _get_access_token(self._sa_info())
        client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        return client, token

    async def validate_config(self) -> tuple[bool, str]:
        required = ["service_account_json"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            return False, f"Missing config keys: {missing}"
        try:
            sa = self._sa_info()
            if "client_email" not in sa or "private_key" not in sa:
                return False, "service_account_json must contain client_email and private_key"
            await _get_access_token(sa)
            return True, ""
        except Exception as e:
            return False, str(e)

    async def list_documents(self) -> list[RemoteDocument]:
        client, _ = await self._client_with_token()
        mime_types = self._mime_filter()
        folder_id = self.config.get("folder_id", "")

        q_parts = [f"mimeType='{m}'" for m in mime_types]
        q = "(" + " or ".join(q_parts) + ") and trashed=false"
        if folder_id:
            q += f" and '{folder_id}' in parents"

        results: list[RemoteDocument] = []
        page_token: str | None = None

        async with client:
            while True:
                params: dict = {
                    "q": q,
                    "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
                    "pageSize": 200,
                }
                if page_token:
                    params["pageToken"] = page_token

                r = await client.get(f"{_DRIVE_API}/files", params=params)
                r.raise_for_status()
                data = r.json()

                for f in data.get("files", []):
                    results.append(RemoteDocument(
                        external_id=f["id"],
                        title=f.get("name", f["id"]),
                        source_url=f.get("webViewLink", f"https://drive.google.com/file/d/{f['id']}"),
                        updated_at=f.get("modifiedTime", ""),
                    ))

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        return results

    async def fetch_document(self, external_id: str) -> ConnectorDocument:
        client, _ = await self._client_with_token()

        async with client:
            # Get file metadata
            meta_r = await client.get(
                f"{_DRIVE_API}/files/{external_id}",
                params={"fields": "id,name,mimeType,modifiedTime,webViewLink"},
            )
            meta_r.raise_for_status()
            meta = meta_r.json()
            mime = meta.get("mimeType", "")
            title = meta.get("name", external_id)

            # Export or download
            export_mime = _EXPORT_MIME.get(mime)
            if export_mime:
                # Google Workspace format — export as plain text
                r = await client.get(
                    _EXPORT_URL.format(id=external_id),
                    params={"mimeType": export_mime},
                )
            else:
                # Binary file — download directly
                r = await client.get(_DOWNLOAD_URL.format(id=external_id))

            r.raise_for_status()

            if mime == "application/pdf":
                # Extract text from PDF bytes
                try:
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(r.content))
                    text = "\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                except Exception:
                    text = r.text
            else:
                text = r.text

            # Strip null bytes (asyncpg rejects them)
            text = re.sub(r"\x00", "", text)

        return ConnectorDocument(
            external_id=external_id,
            title=title,
            text=text,
            source_url=meta.get("webViewLink", f"https://drive.google.com/file/d/{external_id}"),
            metadata={
                "mime_type": mime,
                "updated_at": meta.get("modifiedTime", ""),
                "source": "gdrive",
            },
        )
