"""
Jira action tools — create and triage issues.

Reads connector config from the org's Jira connector in the DB.
"""
import httpx

from rag_chatbot.db.connection import get_pool
from rag_chatbot.agent.actions.registry import ActionResult, register_action


async def _get_jira_config(org_id: int | None) -> dict | None:
    if not org_id:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT config FROM connectors WHERE org_id=$1 AND connector_type='jira' AND is_active=TRUE LIMIT 1",
            org_id,
        )
    if not row:
        return None
    import json as _json
    cfg = row["config"]
    return cfg if isinstance(cfg, dict) else _json.loads(cfg)


@register_action("jira_create_issue")
async def create_issue(params: dict, state) -> ActionResult:
    """
    Create a Jira issue.
    params: {summary, description?, project_key, issue_type? (Bug|Task|Story), priority? (High|Medium|Low)}
    """
    cfg = await _get_jira_config(state.get("org_id"))
    if not cfg:
        return ActionResult(success=False, message="No Jira connector configured for this org.")

    base = cfg["base_url"].rstrip("/")
    project_key = params.get("project_key") or cfg.get("project_key", "")
    if not project_key:
        return ActionResult(success=False, message="project_key is required to create a Jira issue.")

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": params.get("summary", "Issue created via RAG agent"),
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": params.get("description", "")}
                ]}],
            },
            "issuetype": {"name": params.get("issue_type", "Task")},
            "priority": {"name": params.get("priority", "Medium")},
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/rest/api/3/issue",
                auth=(cfg["username"], cfg["api_token"]),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            key = data.get("key", "")
            link = f"{base}/browse/{key}"
            return ActionResult(
                success=True,
                message=f"Jira issue {key} created.",
                data={"key": key, "id": data.get("id"), "link": link},
            )
    except Exception as e:
        return ActionResult(success=False, message=f"Failed to create Jira issue: {e}")


@register_action("jira_triage_issue")
async def triage_issue(params: dict, state) -> ActionResult:
    """
    Triage an existing Jira issue — transition it + add a comment.
    params: {issue_key, transition_name? (In Progress|Done|To Do), comment?}
    """
    cfg = await _get_jira_config(state.get("org_id"))
    if not cfg:
        return ActionResult(success=False, message="No Jira connector configured for this org.")

    base = cfg["base_url"].rstrip("/")
    issue_key = params.get("issue_key", "")
    if not issue_key:
        return ActionResult(success=False, message="issue_key is required to triage.")

    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        auth = (cfg["username"], cfg["api_token"])
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        # Get available transitions
        tr_resp = await client.get(f"{base}/rest/api/3/issue/{issue_key}/transitions", auth=auth, headers=headers)
        if tr_resp.status_code == 200:
            target_name = params.get("transition_name", "In Progress")
            transitions = tr_resp.json().get("transitions", [])
            match = next((t for t in transitions if t["name"].lower() == target_name.lower()), None)
            if match:
                await client.post(
                    f"{base}/rest/api/3/issue/{issue_key}/transitions",
                    auth=auth, headers=headers,
                    json={"transition": {"id": match["id"]}},
                )
                results.append(f"Transitioned to '{match['name']}'")

        # Add comment if provided
        if params.get("comment"):
            await client.post(
                f"{base}/rest/api/3/issue/{issue_key}/comment",
                auth=auth, headers=headers,
                json={"body": {"type": "doc", "version": 1, "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": params["comment"]}]}
                ]}},
            )
            results.append("Comment added")

    msg = f"Issue {issue_key} triaged: {'; '.join(results) if results else 'no changes made'}."
    return ActionResult(success=True, message=msg, data={"issue_key": issue_key})
