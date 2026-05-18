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


@register_action("servicenow_resolve_incident")
async def resolve_incident(params: dict, state) -> ActionResult:
    """
    Resolve / close an existing ServiceNow incident.
    params: {incident_number?, sys_id?, resolution_notes?}
    If neither is provided the most-recent incident from the conversation is used.
    """
    cfg = await _get_snow_config(state.get("org_id"))
    if not cfg:
        return ActionResult(success=False, message="No ServiceNow connector configured for this org.")

    # Allow caller to pass sys_id directly or look it up by number
    sys_id = params.get("sys_id")
    incident_number = params.get("incident_number") or params.get("number")

    # Fall back: scan message history for the most-recently mentioned INC number
    if not sys_id and not incident_number:
        import re as _re
        for msg in reversed(state.get("messages", [])):
            m = _re.search(r"\bINC\d+\b", msg.get("content", ""), _re.IGNORECASE)
            if m:
                incident_number = m.group(0).upper()
                break

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            base = cfg["instance_url"].rstrip("/")
            auth = (cfg["username"], cfg["password"])
            headers = {"Accept": "application/json", "Content-Type": "application/json"}

            # Look up sys_id by incident number if we don't have it
            if not sys_id and incident_number:
                resp = await client.get(
                    f"{base}/api/now/table/incident",
                    auth=auth,
                    headers=headers,
                    params={"sysparm_query": f"number={incident_number}", "sysparm_fields": "sys_id,number", "sysparm_limit": 1},
                )
                resp.raise_for_status()
                records = resp.json().get("result", [])
                if not records:
                    return ActionResult(success=False, message=f"Incident {incident_number} not found.")
                sys_id = records[0]["sys_id"]

            if not sys_id:
                return ActionResult(success=False, message="Could not determine which incident to resolve. Please specify the incident number.")

            # Resolve: state=6 (Resolved) in ServiceNow
            patch_payload = {
                "state": "6",
                "close_code": "Solved (Permanently)",
                "close_notes": params.get("resolution_notes", "Resolved via RAG agent."),
            }
            r = await client.patch(
                f"{base}/api/now/table/incident/{sys_id}",
                auth=auth,
                headers=headers,
                json=patch_payload,
            )
            r.raise_for_status()
            result = r.json()["result"]
            number = result.get("number", incident_number or sys_id)
            return ActionResult(
                success=True,
                message=f"Incident {number} has been resolved successfully.",
                data={"number": number, "sys_id": sys_id},
            )
    except Exception as e:
        return ActionResult(success=False, message=f"Failed to resolve incident: {e}")


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
