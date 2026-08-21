"""
Organisations repository — database access for organizations and app_config.

All SQL queries touching organizations and app_config (per-org LLM/runtime
settings) live here. Route handlers import these typed async functions instead
of writing SQL inline.
"""

import asyncpg


async def get_default_org_id(conn: asyncpg.Connection) -> int | None:
    """
    Return the id of the 'default' organisation, or None if it doesn't exist.

    Args:
        conn: Active asyncpg connection or pool connection.

    Returns:
        Integer org id, or None.
    """
    return await conn.fetchval("SELECT id FROM organizations WHERE slug='default'")


async def get_org_llm_config(
    conn: asyncpg.Connection,
    org_id: int,
) -> dict[str, str]:
    """
    Fetch all key/value config rows for an org and return them as a dict.

    Args:
        conn: Active asyncpg connection or pool connection.
        org_id: The organisation whose config to retrieve.

    Returns:
        Mapping of config key → value strings (empty dict when org has no config).
    """
    rows = await conn.fetch("SELECT key, value FROM app_config WHERE org_id=$1", org_id)
    return {r["key"]: r["value"] for r in rows}


async def resolve_org_id(
    conn: asyncpg.Connection,
    *,
    user_org_id: int | None,
    request_org_id: int | None,
) -> int | None:
    """
    Resolve the effective org_id using the priority chain: user org > request override > default.

    Args:
        conn: Active asyncpg connection or pool connection.
        user_org_id: The authenticated user's own org (highest priority).
        request_org_id: Explicit org override from the request body (superadmin use).

    Returns:
        Resolved org_id, or None if no default org exists.
    """
    if user_org_id:
        return user_org_id
    if request_org_id:
        return request_org_id
    return await get_default_org_id(conn)


async def get_sn_connector_config(
    conn: asyncpg.Connection,
    org_id: int | None,
) -> asyncpg.Record | None:
    """
    Return the active ServiceNow connector row for the given org.

    Args:
        conn: Active asyncpg connection or pool connection.
        org_id: Org to look up; None means any active connector.

    Returns:
        A record with a 'config' field (JSON string or dict), or None if not found.
    """
    return await conn.fetchrow(
        """
        SELECT config FROM connectors
        WHERE connector_type = 'servicenow'
          AND is_active = true
          AND ($1::bigint IS NULL OR org_id = $1)
        ORDER BY id
        LIMIT 1
        """,
        org_id,
    )
