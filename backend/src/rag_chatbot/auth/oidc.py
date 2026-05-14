"""
OIDC token validation for Zitadel (and any standard OIDC provider).

Responsibilities
----------------
- Fetch and cache the provider's JWKS (public keys).
- Validate RS256 JWTs issued by Zitadel.
- Return a normalised user dict compatible with the local-auth user dict so
  the rest of the stack (deps.require_user) needs no extra branching.

The JWKS is cached for JWKS_TTL_SECONDS and refreshed lazily on the next
request after expiry.  No background thread — this keeps the module simple.
"""
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient, PyJWKClientError

from rag_chatbot.config import settings

# ---------------------------------------------------------------------------
# JWKS client — one instance per process, lazily initialised
# ---------------------------------------------------------------------------

_jwks_client: PyJWKClient | None = None
_jwks_client_issuer: str = ""  # tracks which issuer the client was built for


def _get_jwks_client() -> PyJWKClient:
    """Return (or create) a PyJWKClient pointed at the configured Zitadel issuer."""
    global _jwks_client, _jwks_client_issuer

    issuer = settings.zitadel_issuer.rstrip("/")
    if _jwks_client is None or _jwks_client_issuer != issuer:
        jwks_uri = f"{issuer}/oauth/v2/keys"
        # cache_keys=True means PyJWT re-fetches only when a key is unknown
        _jwks_client = PyJWKClient(jwks_uri, cache_keys=True)
        _jwks_client_issuer = issuer

    return _jwks_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def oidc_enabled() -> bool:
    """True when a Zitadel issuer is configured."""
    return bool(settings.zitadel_issuer)


async def validate_oidc_token(raw_token: str) -> dict[str, Any]:
    """
    Validate a Zitadel-issued JWT and return a user dict.

    Returns
    -------
    dict with keys: id, email, name, role, org_id, is_active
        - id       : Zitadel subject claim (string used as a stable identifier)
        - email    : from the "email" claim
        - name     : from "name" or "preferred_username"
        - role     : "member" by default; elevated to "admin" via Zitadel roles
        - org_id   : None (org mapping happens via email-domain rules or Zitadel
                     organisation claims — extend _map_org_id() as needed)
        - is_active: always True for valid tokens

    Raises
    ------
    jwt.InvalidTokenError  on any validation failure (expired, wrong issuer, etc.)
    """
    if not oidc_enabled():
        raise jwt.InvalidTokenError("OIDC not configured")

    client = _get_jwks_client()

    try:
        signing_key = client.get_signing_key_from_jwt(raw_token)
    except PyJWKClientError as exc:
        raise jwt.InvalidTokenError(f"JWKS fetch/key lookup failed: {exc}") from exc

    issuer = settings.zitadel_issuer.rstrip("/")

    # Validate audience when the backend client ID is configured.
    # Zitadel sets `aud` to the frontend client ID by default; the backend
    # client ID is added when the token is requested with the correct scope.
    # During initial setup, leave ZITADEL_BACKEND_CLIENT_ID empty to skip.
    backend_client_id = settings.zitadel_backend_client_id
    decode_options: dict = {"verify_aud": bool(backend_client_id)}
    audience = [backend_client_id] if backend_client_id else None

    payload = jwt.decode(
        raw_token,
        signing_key.key,
        algorithms=["RS256"],
        options=decode_options,
        issuer=issuer,
        audience=audience,
    )

    return _claims_to_user(payload)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _claims_to_user(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Zitadel JWT claims → internal user dict."""
    sub = payload.get("sub", "")
    email = payload.get("email", "") or payload.get("preferred_username", "")
    name = payload.get("name") or payload.get("preferred_username") or email

    # Zitadel puts custom roles under "urn:zitadel:iam:org:project:roles"
    # or in a flat "roles" array depending on the app's token settings.
    roles: list[str] = []
    zitadel_roles: Any = payload.get("urn:zitadel:iam:org:project:roles", {})
    if isinstance(zitadel_roles, dict):
        roles = list(zitadel_roles.keys())
    elif isinstance(zitadel_roles, list):
        roles = zitadel_roles

    role = "admin" if "admin" in roles or "superadmin" in roles else "member"

    return {
        "id": sub,           # string, not int — callers that need int should cast
        "email": email,
        "name": name,
        "role": role,
        "org_id": _map_org_id(payload),
        "is_active": True,
    }


def _map_org_id(payload: dict[str, Any]) -> int | None:
    """
    Derive the internal org_id from Zitadel claims.

    Priority order:
    1. "knowledge_mesh_org_id" custom claim (set via Zitadel action/mapping)
    2. Not yet mapped → None (user lands in default org)

    Extend this function to add email-domain → org mapping or Zitadel org ID
    → internal org ID lookup as your multi-tenancy setup evolves.
    """
    custom = payload.get("knowledge_mesh_org_id")
    if custom is not None:
        try:
            return int(custom)
        except (TypeError, ValueError):
            pass
    return None
