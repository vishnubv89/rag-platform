"""
Internal endpoint called by Zitadel Actions during token issuance.

Flow
----
1. Zitadel Action (JS) fires on Pre Token Creation trigger.
2. It POSTs { email } to /internal/zitadel/enrich with X-Zitadel-Secret.
3. We look up org_id and role from org_domains + sso_user_roles.
4. Return { org_id, role } — Zitadel embeds them as custom JWT claims.

Security
--------
The endpoint is reachable only within the Docker/K8s internal network
AND requires X-Zitadel-Secret to match ZITADEL_ACTION_SECRET.
Never expose this path through a public ingress.
"""
import logging

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, EmailStr

from rag_chatbot.config import settings
from rag_chatbot.db.connection import get_pool

router = APIRouter(prefix="/internal/zitadel", tags=["internal"])
_log = logging.getLogger(__name__)


class EnrichRequest(BaseModel):
    email: str


class EnrichResponse(BaseModel):
    org_id: int | None = None
    role: str = "member"


@router.post("/enrich", response_model=EnrichResponse)
async def enrich(
    body: EnrichRequest,
    x_zitadel_secret: str = Header(..., alias="X-Zitadel-Secret"),
) -> EnrichResponse:
    """
    Return the org_id and role for an SSO user based on their email.

    Priority:
      1. sso_user_roles row (explicit per-user override)
      2. org_domains row   (domain default_role)
      3. org_id=None, role="member" fallback
    """
    # Validate shared secret
    if not settings.zitadel_action_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Action secret not configured")
    if x_zitadel_secret != settings.zitadel_action_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid action secret")

    email = body.email.strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Check per-user override first
        user_row = await conn.fetchrow(
            "SELECT org_id, role FROM sso_user_roles WHERE email = $1",
            email,
        )
        if user_row:
            _log.info("enrich: %s → org=%s role=%s (user override)",
                      email, user_row["org_id"], user_row["role"])
            return EnrichResponse(org_id=user_row["org_id"], role=user_row["role"])

        # 2. Fall back to domain default
        if domain:
            domain_row = await conn.fetchrow(
                "SELECT org_id, default_role FROM org_domains WHERE domain = $1",
                domain,
            )
            if domain_row:
                _log.info("enrich: %s → org=%s role=%s (domain default)",
                          email, domain_row["org_id"], domain_row["default_role"])
                return EnrichResponse(
                    org_id=domain_row["org_id"],
                    role=domain_row["default_role"],
                )

    # 3. Unknown user — no org, member role
    _log.info("enrich: %s → no match, returning defaults", email)
    return EnrichResponse(org_id=None, role="member")
