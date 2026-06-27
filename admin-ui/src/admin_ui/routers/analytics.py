import json
from fastapi import APIRouter, Request
from admin_ui import client

router = APIRouter()


@router.get("/analytics")
async def analytics_page(
    request: Request,
    from_dt: str | None = None,
    to_dt: str | None = None,
    page: int = 1,
):
    org_id = request.state.active_org_id
    try:
        summary = await client.analytics_summary(org_id=org_id, from_dt=from_dt, to_dt=to_dt)
        logs = await client.list_logs(org_id=org_id, page=page, from_dt=from_dt, to_dt=to_dt)
        usage = await client.token_usage(org_id=org_id, days=30)
        orgs = await client.list_orgs()
        cfg_resp = await client.get_config(org_id=org_id)
        cfg = cfg_resp.get("config", {})
        gaps: list = []
        if cfg.get("feature_content_gap") == "true":
            gaps = await client.content_gaps(org_id=org_id, days=30)
    except Exception as e:
        summary, logs, usage, orgs, cfg, gaps = {}, {"items": [], "total": 0}, [], [], {}, []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "summary": summary,
            "logs": logs,
            "usage_json": json.dumps(usage),
            "orgs": orgs,
            "active_org_id": org_id,
            "from_dt": from_dt or "",
            "to_dt": to_dt or "",
            "page": page,
            "active_page": "analytics",
            "config": cfg,
            "gaps": gaps,
        },
    )
