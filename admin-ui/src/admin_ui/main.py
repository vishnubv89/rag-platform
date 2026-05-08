from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import admin_ui.client as api
from admin_ui.routers import dashboard, documents, settings, orgs, analytics, connectors, knowledge, users, audit

app = FastAPI(title="RAG Admin UI", docs_url=None, redoc_url=None)

_base = Path(__file__).parent
templates = Jinja2Templates(directory=str(_base / "templates"))
app.state.templates = templates

app.include_router(dashboard.router)
app.include_router(documents.router)
app.include_router(settings.router)
app.include_router(orgs.router)
app.include_router(analytics.router)
app.include_router(connectors.router)
app.include_router(knowledge.router)
app.include_router(users.router)
app.include_router(audit.router)


@app.middleware("http")
async def attach_globals(request: Request, call_next):
    request.state.error = None
    request.state.success = None
    # Inject org list globally so base.html sidebar can render the org switcher
    # without each router having to pass it explicitly.
    try:
        request.state.all_orgs = await api.list_orgs()
    except Exception:
        request.state.all_orgs = []
    return await call_next(request)
