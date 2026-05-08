from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

import admin_ui.client as api

router = APIRouter()


@router.get("/knowledge")
async def knowledge_health_page(request: Request, org_id: str | None = None):
    org_id = int(org_id) if org_id else None
    templates = request.app.state.templates
    try:
        health = await api.knowledge_health(org_id=org_id)
        conflicts = await api.list_conflicts(status="pending", org_id=org_id)
        stale = await api.stale_documents(days=90, org_id=org_id)
        orgs = await api.list_orgs()
        error = None
    except Exception as e:
        health, conflicts, stale, orgs, error = {}, [], [], [], str(e)
    return templates.TemplateResponse(request, "knowledge.html", {
        "health": health,
        "conflicts": conflicts,
        "stale": stale,
        "orgs": orgs,
        "active_org_id": org_id,
        "error": error,
        "active_page": "knowledge",
    })


@router.post("/knowledge/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: int, org_id: str | None = Form(None)):
    org_id = int(org_id) if org_id else None
    await api.resolve_conflict(conflict_id, status="resolved")
    redirect = f"/knowledge?org_id={org_id}" if org_id else "/knowledge"
    return RedirectResponse(redirect, status_code=303)


@router.post("/knowledge/conflicts/{conflict_id}/dismiss")
async def dismiss_conflict(conflict_id: int, org_id: str | None = Form(None)):
    org_id = int(org_id) if org_id else None
    await api.resolve_conflict(conflict_id, status="dismissed")
    redirect = f"/knowledge?org_id={org_id}" if org_id else "/knowledge"
    return RedirectResponse(redirect, status_code=303)
