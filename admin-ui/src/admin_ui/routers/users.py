from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from admin_ui import client

router = APIRouter()


@router.get("/users")
async def users_page(request: Request, org_id: str | None = None):
    org_id = int(org_id) if org_id else None
    try:
        users = await client.list_users(org_id=org_id)
        orgs = await client.list_orgs()
        error = None
    except Exception as e:
        users, orgs, error = [], [], str(e)
    return request.app.state.templates.TemplateResponse(request, "users.html", {
        "users": users,
        "orgs": orgs,
        "active_page": "users",
        "active_org_id": org_id,
        "error": error,
    })


@router.post("/users/create")
async def create_user(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    role: str = Form("member"),
    org_id: int | None = Form(None),
):
    redirect = f"/users{f'?org_id={org_id}' if org_id else ''}"
    try:
        await client.create_user(email=email, name=name, password=password,
                                 role=role, org_id=org_id)
    except Exception as e:
        request.state.error = str(e)
    return RedirectResponse(redirect, status_code=303)


@router.post("/users/{user_id}/toggle")
async def toggle_user(user_id: int, is_active: str = Form("true"), org_id: str | None = Form(None)):
    org_id = int(org_id) if org_id else None
    await client.patch_user(user_id, is_active=(is_active == "true"))
    return RedirectResponse(f"/users{f'?org_id={org_id}' if org_id else ''}", status_code=303)


@router.post("/users/{user_id}/delete")
async def delete_user(user_id: int, org_id: str | None = Form(None)):
    org_id = int(org_id) if org_id else None
    await client.delete_user(user_id)
    return RedirectResponse(f"/users{f'?org_id={org_id}' if org_id else ''}", status_code=303)
