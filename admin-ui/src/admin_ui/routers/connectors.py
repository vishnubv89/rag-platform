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
async def connectors_page(request: Request):
    templates = request.app.state.templates
    try:
        connectors = await api.list_connectors()
        types = await api.connector_types()
        error = None
    except Exception as e:
        connectors, types, error = [], [], str(e)
    return templates.TemplateResponse(request, "connectors.html", {
        "connectors": connectors,
        "connector_types": types,
        "config_fields": CONFIG_FIELDS,
        "error": error,
    })


@router.post("/connectors/create")
async def create_connector(
    request: Request,
    name: str = Form(...),
    connector_type: str = Form(...),
    sync_interval_minutes: int = Form(60),
):
    form = await request.form()
    # Build config from form fields for the selected type
    fields = CONFIG_FIELDS.get(connector_type, [])
    config = {f: form.get(f"config_{f}", "") for f in fields if form.get(f"config_{f}", "")}
    try:
        await api.create_connector(
            name=name,
            connector_type=connector_type,
            config=config,
            sync_interval_minutes=sync_interval_minutes,
            org_id=None,
        )
    except Exception as e:
        templates = request.app.state.templates
        connectors = await api.list_connectors()
        types = await api.connector_types()
        return templates.TemplateResponse(request, "connectors.html", {
            "connectors": connectors,
            "connector_types": types,
            "config_fields": CONFIG_FIELDS,
            "error": str(e),
        })
    return RedirectResponse("/connectors", status_code=303)


@router.get("/connectors/{connector_id}")
async def connector_detail(request: Request, connector_id: int):
    templates = request.app.state.templates
    try:
        connector = await api.get_connector(connector_id)
        error = None
    except Exception as e:
        connector, error = {}, str(e)
    return templates.TemplateResponse(request, "connector_detail.html", {
        "connector": connector,
        "config_fields": CONFIG_FIELDS,
        "error": error,
    })


@router.post("/connectors/{connector_id}/sync")
async def trigger_sync(connector_id: int):
    await api.trigger_sync(connector_id)
    return RedirectResponse(f"/connectors/{connector_id}", status_code=303)


@router.post("/connectors/{connector_id}/toggle")
async def toggle_connector(connector_id: int, request: Request):
    form = await request.form()
    is_active = form.get("is_active") == "true"
    await api.patch_connector(connector_id, is_active=is_active)
    return RedirectResponse(f"/connectors/{connector_id}", status_code=303)


@router.post("/connectors/{connector_id}/delete")
async def delete_connector(connector_id: int):
    await api.delete_connector(connector_id)
    return RedirectResponse("/connectors", status_code=303)
