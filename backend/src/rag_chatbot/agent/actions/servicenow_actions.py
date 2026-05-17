"""
ServiceNow action tools — create incidents and change requests.

Reads connector config from the org's ServiceNow connector in the DB.
"""
import httpx

from rag_chatbot.db.connection import get_pool
from rag_chatbot.agent.actions.registry import ActionResult, register_action


async def _get_snow_config(org_id: int | None) -> dict | None:
    if not org_id:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT config FROM connectors
               WHERE org_id=$1 AND connector_type='servicenow' AND is_active=TRUE
               LIMIT 1""",
            org_id,
        )
    if not row:
        return None
    import json as _json
    cfg = row["config"]
    return cfg if isinstance(cfg, dict) else _json.loads(cfg)


@register_action("servicenow_create_incident")
async def create_incident(params: dict, state) -> ActionResult:
    """
    Create a ServiceNow incident.
    params: {short_description, description?, urgency? (1=high,2=medium,3=low), category?}
    """
    cfg = await _get_snow_config(state.get("org_id"))
    if not cfg:
        return ActionResult(success=False, message="No ServiceNow connector configured for this org.")

    payload = {
        "short_description": params.get("short_description", "Incident created via RAG agent"),
        "description": params.get("description", ""),
        "urgency": str(params.get("urgency", "2")),
        "category": params.get("category", "inquiry"),
        "caller_id": "system",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{cfg['instance_url'].rstrip('/')}/api/now/table/incident",
                auth=(cfg["username"], cfg["password"]),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            result = r.json()["result"]
            number = result.get("number", "")
            sys_id = result.get("sys_id", "")
            link = f"{cfg['instance_url']}/nav_to.do?uri=incident.do?sys_id={sys_id}"
            return ActionResult(
                success=True,
                message=f"Incident {number} created successfully.",
                data={"number": number, "sys_id": sys_id, "link": link},
            )
    except Exception as e:
        return ActionResult(success=False, message=f"Failed to create incident: {e}")


@register_action("servicenow_create_change")
async def create_change_request(params: dict, state) -> ActionResult:
    """
    Create a ServiceNow change request.
    params: {short_description, description?, type? (normal|standard|emergency)}
    """
    cfg = await _get_snow_config(state.get("org_id"))
    if not cfg:
        return ActionResult(success=False, message="No ServiceNow connector configured for this org.")

    payload = {
        "short_description": params.get("short_description", "Change request via RAG agent"),
        "description": params.get("description", ""),
        "type": params.get("type", "normal"),
        "category": "Other",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{cfg['instance_url'].rstrip('/')}/api/now/table/change_request",
                auth=(cfg["username"], cfg["password"]),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            result = r.json()["result"]
            number = result.get("number", "")
            sys_id = result.get("sys_id", "")
            link = f"{cfg['instance_url']}/nav_to.do?uri=change_request.do?sys_id={sys_id}"
            return ActionResult(
                success=True,
                message=f"Change request {number} created.",
                data={"number": number, "sys_id": sys_id, "link": link},
            )
    except Exception as e:
        return ActionResult(success=False, message=f"Failed to create change request: {e}")
