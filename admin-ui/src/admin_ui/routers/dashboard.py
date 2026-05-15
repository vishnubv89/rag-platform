from fastapi import APIRouter, Request
from admin_ui import client

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    org_id = request.state.active_org_id
    try:
        summary = await client.analytics_summary(org_id=org_id)
        docs = await client.list_docs(org_id=org_id, limit=5)
        logs = await client.list_logs(org_id=org_id, page=1)
        orgs = await client.list_orgs()
    except Exception as e:
        summary, docs, logs, orgs = {}, {"items": []}, {"items": []}, []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "summary": summary,
            "recent_docs": docs.get("items", []),
            "recent_logs": logs.get("items", []),
            "orgs": orgs,
            "active_org_id": org_id,
            "active_page": "dashboard",
        },
    )
