from pathlib import Path
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import admin_ui.client as api
from admin_ui.config import settings
from admin_ui.routers import (
    auth_router, dashboard, documents,
    settings as settings_router, orgs,
    analytics, connectors, knowledge, users, audit,
)

app = FastAPI(title="RAG Admin UI", docs_url=None, redoc_url=None)

_base = Path(__file__).parent
templates = Jinja2Templates(directory=str(_base / "templates"))
app.state.templates = templates

app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(documents.router)
app.include_router(settings_router.router)
app.include_router(orgs.router)
app.include_router(analytics.router)
app.include_router(connectors.router)
app.include_router(knowledge.router)
app.include_router(users.router)
app.include_router(audit.router)

# Public paths that bypass auth check
_PUBLIC = {"/login", "/logout"}


@app.middleware("http")
async def attach_globals(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC:
        return await call_next(request)

    # Auth gate — redirect to login if no session
    user = request.session.get("user")
    if not user:
        return RedirectResponse(f"/login?next={path}")

    request.state.user = user
    request.state.error = None

    # Resolve active org: URL param overrides cookie, cookie persists across pages
    org_id_str = request.query_params.get("org_id")
    if org_id_str is not None:
        request.state.active_org_id = int(org_id_str) if org_id_str else None
    else:
        cookie_val = request.cookies.get("admin_org_scope")
        request.state.active_org_id = int(cookie_val) if cookie_val else None

    try:
        request.state.all_orgs = await api.list_orgs()
    except Exception:
        request.state.all_orgs = []

    response = await call_next(request)

    # Sync URL org param into cookie so it persists for future navigations
    if org_id_str is not None:
        if org_id_str:
            response.set_cookie(
                "admin_org_scope", org_id_str,
                httponly=True, samesite="lax", max_age=30 * 24 * 3600, path="/",
            )
        else:
            response.delete_cookie("admin_org_scope", path="/")

    return response


@app.post("/set-org")
async def set_org(org_id: str = Form(""), redirect_to: str = Form("/")):
    """Switch active org scope — stores in cookie, no URL param needed."""
    response = RedirectResponse(redirect_to, status_code=303)
    if org_id:
        response.set_cookie(
            "admin_org_scope", org_id,
            httponly=True, samesite="lax", max_age=30 * 24 * 3600, path="/",
        )
    else:
        response.delete_cookie("admin_org_scope", path="/")
    return response


# SessionMiddleware must be added AFTER @middleware decorator so it becomes
# the outermost layer and populates request.session before attach_globals runs.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="admin_session",
    max_age=8 * 3600,
    https_only=False,
    same_site="lax",
)
