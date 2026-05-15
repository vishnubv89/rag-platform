from fastapi import APIRouter, Request
from admin_ui import client

router = APIRouter()


@router.get("/audit")
async def audit_page(request: Request, offset: int = 0):
    org_id = request.state.active_org_id
    try:
        data = await client.list_audit(org_id=org_id, limit=50, offset=offset)
        orgs = await client.list_orgs()
        error = None
    except Exception as e:
        data, orgs, error = {"total": 0, "items": []}, [], str(e)
    return request.app.state.templates.TemplateResponse(request, "audit.html", {
        "logs": data["items"],
        "total": data["total"],
        "orgs": orgs,
        "active_org_id": org_id,
        "offset": offset,
        "limit": 50,
        "active_page": "audit",
        "error": error,
    })
