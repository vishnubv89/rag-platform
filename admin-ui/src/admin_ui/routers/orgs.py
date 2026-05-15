from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from admin_ui import client

router = APIRouter()


@router.get("/orgs")
async def list_orgs_page(request: Request):
    try:
        orgs = await client.list_orgs()
    except Exception as e:
        orgs = []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "orgs.html",
        {"orgs": orgs, "active_page": "orgs"},
    )


@router.post("/orgs")
async def create_org(name: str = Form(...), slug: str = Form(...)):
    await client.create_org(name=name, slug=slug)
    return RedirectResponse("/orgs", status_code=303)


@router.get("/orgs/{org_id}")
async def org_detail(request: Request, org_id: int, new_key: str | None = None):
    try:
        org = await client.get_org(org_id)
        keys = await client.list_keys(org_id)
        sso_roles = await client.list_sso_roles(org_id)
    except Exception as e:
        org, keys, sso_roles = {}, [], []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "org_detail.html",
        {
            "org": org,
            "keys": keys,
            "sso_roles": sso_roles,
            "new_key": new_key,
            "active_page": "orgs",
        },
    )


@router.post("/orgs/{org_id}/keys")
async def generate_key(org_id: int, label: str = Form("")):
    result = await client.create_key(org_id=org_id, label=label)
    raw_key = result.get("key", "")
    return RedirectResponse(f"/orgs/{org_id}?new_key={raw_key}", status_code=303)


@router.post("/orgs/{org_id}/keys/{key_id}/revoke")
async def revoke_key(org_id: int, key_id: int):
    await client.revoke_key(org_id=org_id, key_id=key_id)
    return RedirectResponse(f"/orgs/{org_id}", status_code=303)


@router.post("/orgs/{org_id}/toggle")
async def toggle_org(org_id: int, is_active: str = Form("true")):
    await client.patch_org(org_id, is_active=(is_active == "true"))
    return RedirectResponse("/orgs", status_code=303)


# ── SSO Role Management ───────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/sso-roles")
async def add_sso_role(org_id: int, email: str = Form(...), role: str = Form(...)):
    await client.upsert_sso_role(org_id=org_id, email=email, role=role)
    return RedirectResponse(f"/orgs/{org_id}#sso-roles", status_code=303)


@router.post("/orgs/{org_id}/sso-roles/{email}/delete")
async def remove_sso_role(org_id: int, email: str):
    await client.delete_sso_role(org_id=org_id, email=email)
    return RedirectResponse(f"/orgs/{org_id}#sso-roles", status_code=303)
