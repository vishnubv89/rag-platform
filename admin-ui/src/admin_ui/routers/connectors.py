import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

import admin_ui.client as api

router = APIRouter()

CONFIG_FIELDS = {
    "servicenow": ["instance_url", "username", "password", "kb_sys_id"],
    "sharepoint": ["tenant_id", "client_id", "client_secret", "site_url", "folder_path"],
    "confluence": ["base_url", "username", "api_token", "space_key"],
    "manual": [],
}


@router.get("/connectors")
async def connectors_page(request: Request, org_id: int | None = None):
    templates = request.app.state.templates
    try:
        connectors = await api.list_connectors(org_id=org_id)
        types = await api.connector_types()
        orgs = await api.list_orgs()
        error = None
    except Exception as e:
        connectors, types, orgs, error = [], [], [], str(e)
    return templates.TemplateResponse(request, "connectors.html", {
        "connectors": connectors,
        "connector_types": types,
        "config_fields": CONFIG_FIELDS,
        "orgs": orgs,
        "active_org_id": org_id,
        "error": error,
    })


@router.post("/connectors/create")
async def create_connector(
    request: Request,
    name: str = Form(...),
    connector_type: str = Form(...),
    sync_interval_minutes: int = Form(60),
    org_id: int | None = Form(None),
):
    form = await request.form()
    fields = CONFIG_FIELDS.get(connector_type, [])
    config = {f: form.get(f"config_{f}", "") for f in fields if form.get(f"config_{f}", "")}
    redirect = f"/connectors?org_id={org_id}" if org_id else "/connectors"
    try:
        await api.create_connector(
            name=name,
            connector_type=connector_type,
            config=config,
            sync_interval_minutes=sync_interval_minutes,
            org_id=org_id,
        )
    except Exception as e:
        templates = request.app.state.templates
        connectors = await api.list_connectors(org_id=org_id)
        types = await api.connector_types()
        orgs = await api.list_orgs()
        return templates.TemplateResponse(request, "connectors.html", {
            "connectors": connectors,
            "connector_types": types,
            "config_fields": CONFIG_FIELDS,
            "orgs": orgs,
            "active_org_id": org_id,
            "error": str(e),
        })
    return RedirectResponse(redirect, status_code=303)


@router.get("/connectors/{connector_id}")
async def connector_detail(request: Request, connector_id: int, org_id: int | None = None):
    templates = request.app.state.templates
    try:
        connector = await api.get_connector(connector_id)
        error = None
    except Exception as e:
        connector, error = {}, str(e)
    return templates.TemplateResponse(request, "connector_detail.html", {
        "connector": connector,
        "config_fields": CONFIG_FIELDS,
        "active_org_id": org_id,
        "error": error,
    })


@router.post("/connectors/{connector_id}/sync")
async def trigger_sync(connector_id: int, org_id: int | None = Form(None)):
    await api.trigger_sync(connector_id)
    redirect = f"/connectors/{connector_id}?org_id={org_id}" if org_id else f"/connectors/{connector_id}"
    return RedirectResponse(redirect, status_code=303)


@router.post("/connectors/{connector_id}/toggle")
async def toggle_connector(connector_id: int, request: Request):
    form = await request.form()
    is_active = form.get("is_active") == "true"
    org_id = form.get("org_id")
    org_id_int = int(org_id) if org_id else None
    await api.patch_connector(connector_id, org_id=org_id_int, is_active=is_active)
    redirect = f"/connectors/{connector_id}?org_id={org_id}" if org_id else f"/connectors/{connector_id}"
    return RedirectResponse(redirect, status_code=303)


@router.post("/connectors/{connector_id}/delete")
async def delete_connector(connector_id: int, org_id: int | None = Form(None)):
    await api.delete_connector(connector_id, org_id=org_id)
    redirect = f"/connectors?org_id={org_id}" if org_id else "/connectors"
    return RedirectResponse(redirect, status_code=303)
