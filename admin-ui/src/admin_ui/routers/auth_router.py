from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

import admin_ui.client as api

router = APIRouter()

_ALLOWED_ROLES = {"superadmin", "admin"}


@router.get("/login")
async def login_page(request: Request, next: str = "/", error: str | None = None):
    return request.app.state.templates.TemplateResponse(
        request, "login.html", {"next": next, "error": error}
    )


@router.post("/login")
async def do_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    try:
        token_data = await api.login(email=email, password=password)
        user_info = await api.me(access_token=token_data["access_token"])
    except Exception as exc:
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"next": next, "error": str(exc) or "Invalid credentials"},
            status_code=401,
        )

    if user_info.get("role") not in _ALLOWED_ROLES:
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"next": next, "error": "Access denied — admin role required."},
            status_code=403,
        )

    request.session["user"] = {
        "id": user_info["id"],
        "email": user_info["email"],
        "name": user_info["name"],
        "role": user_info["role"],
    }
    return RedirectResponse(next or "/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("admin_org_scope", path="/")
    return response
