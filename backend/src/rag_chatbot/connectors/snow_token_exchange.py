"""
ServiceNow OAuth 2.0 On-Behalf-Of (OBO) token exchange.

What it does
------------
Takes the user's Zitadel access token and exchanges it for a ServiceNow
OAuth token using RFC 8693 Token Exchange.  The resulting token is tied to
the user's ServiceNow identity, so any KB search made with it respects that
user's ServiceNow ACLs — only articles they can read in ServiceNow will be
returned.

Prerequisites (ServiceNow admin steps)
--------------------------------------
See docs/sso-obo-setup.md for the full walkthrough.  In brief:

1. In ServiceNow, create an OAuth 2.0 application record with:
     Grant type: Token Exchange (urn:ietf:params:oauth:grant-type:token-exchange)
     Client ID:  <copy to SN_OBO_CLIENT_ID>
     Client Secret: <copy to SN_OBO_CLIENT_SECRET>

2. Add Zitadel as a trusted identity provider in that OAuth app:
     Issuer: the value of ZITADEL_ISSUER in your .env
     JWKS URI: <ZITADEL_ISSUER>/oauth/v2/keys

3. The token exchange endpoint is:
     <instance_url>/oauth_token.do

Usage
-----
    from rag_chatbot.connectors.snow_token_exchange import exchange_for_snow_token

    snow_token = await exchange_for_snow_token(user_zitadel_token, connector_config)
    if snow_token:
        # use snow_token in Authorization header for ServiceNow API calls
        headers = {"Authorization": f"Bearer {snow_token}"}
"""
import logging

import httpx

logger = logging.getLogger(__name__)

# RFC 8693 grant type URI
_TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
_ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


async def exchange_for_snow_token(
    user_token: str,
    connector_config: dict,
) -> str | None:
    """
    Exchange a Zitadel access token for a ServiceNow OAuth token.

    Parameters
    ----------
    user_token
        The raw Zitadel access token from the user's Bearer header.
    connector_config
        The connector's config dict (from the connectors table).
        Must include:
          - instance_url        e.g. https://dev12345.service-now.com
          - obo_client_id       ServiceNow OAuth app client ID
          - obo_client_secret   ServiceNow OAuth app client secret

    Returns
    -------
    str | None
        ServiceNow access token on success, None if OBO is not configured
        for this connector or if the exchange fails.
    """
    instance_url = connector_config.get("instance_url", "").rstrip("/")
    client_id = connector_config.get("obo_client_id", "")
    client_secret = connector_config.get("obo_client_secret", "")

    if not (instance_url and client_id and client_secret):
        # OBO not configured for this connector — fall back to service account
        return None

    token_endpoint = f"{instance_url}/oauth_token.do"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                token_endpoint,
                data={
                    "grant_type": _TOKEN_EXCHANGE_GRANT,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "subject_token": user_token,
                    "subject_token_type": _ACCESS_TOKEN_TYPE,
                    "requested_token_type": _ACCESS_TOKEN_TYPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.RequestError as exc:
        logger.warning("OBO token exchange network error: %s", exc)
        return None

    if resp.status_code != 200:
        logger.warning(
            "OBO token exchange failed: HTTP %s — %s",
            resp.status_code,
            resp.text[:200],
        )
        return None

    data = resp.json()
    token = data.get("access_token")
    if not token:
        logger.warning("OBO response missing access_token: %s", data)
        return None

    logger.info("OBO token exchange succeeded for instance %s", instance_url)
    return token


async def snow_kb_search(
    query: str,
    snow_token: str,
    instance_url: str,
    kb_sys_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Search ServiceNow Knowledge Base directly using a user's OBO token.

    Returns chunks in the same format as hybrid_search so results can be
    merged with pgvector results in retriever_node.

    Parameters
    ----------
    query        Full-text search query.
    snow_token   ServiceNow access token from exchange_for_snow_token().
    instance_url ServiceNow instance base URL.
    kb_sys_id    Optional: restrict search to a specific KB sys_id.
    limit        Max number of articles to return.
    """
    instance_url = instance_url.rstrip("/")
    params: dict = {
        "sysparm_query": f"text CONTAINS {query}^workflow_state=published",
        "sysparm_fields": "sys_id,short_description,text,kb_knowledge_base",
        "sysparm_limit": limit,
    }
    if kb_sys_id:
        params["sysparm_query"] += f"^kb_knowledge_base={kb_sys_id}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{instance_url}/api/now/table/kb_knowledge",
                params=params,
                headers={
                    "Authorization": f"Bearer {snow_token}",
                    "Accept": "application/json",
                },
            )
    except httpx.RequestError as exc:
        logger.warning("OBO KB search network error: %s", exc)
        return []

    if resp.status_code != 200:
        logger.warning("OBO KB search failed: HTTP %s", resp.status_code)
        return []

    results = []
    for article in resp.json().get("result", []):
        text = article.get("text", "") or article.get("short_description", "")
        if not text:
            continue
        results.append({
            # chunk_id / doc_id are unknown for live results; use 0 as sentinel
            "chunk_id": 0,
            "doc_id": 0,
            "doc_title": article.get("short_description", ""),
            "doc_source": f"{instance_url}/kb_view.do?sysparm_article={article['sys_id']}",
            "text": text[:2000],
            "external_id": article.get("sys_id"),
            "score": 1.0,  # live OBO results ranked by SN relevance; no vector score
            "source": "obo_live",
        })

    return results
