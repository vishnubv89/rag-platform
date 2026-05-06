from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

import admin_ui.client as api

router = APIRouter()


@router.get("/knowledge")
async def knowledge_health_page(request: Request):
    templates = request.app.state.templates
    try:
        health = await api.knowledge_health()
        conflicts = await api.list_conflicts(status="pending")
        stale = await api.stale_documents(days=90)
        error = None
    except Exception as e:
        health, conflicts, stale, error = {}, [], [], str(e)
    return templates.TemplateResponse(request, "knowledge.html", {
        "health": health,
        "conflicts": conflicts,
        "stale": stale,
        "error": error,
    })


@router.post("/knowledge/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: int):
    await api.resolve_conflict(conflict_id, status="resolved")
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/conflicts/{conflict_id}/dismiss")
async def dismiss_conflict(conflict_id: int):
    await api.resolve_conflict(conflict_id, status="dismissed")
    return RedirectResponse("/knowledge", status_code=303)
