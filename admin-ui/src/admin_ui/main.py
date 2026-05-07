from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admin_ui.routers import dashboard, documents, settings, orgs, analytics, connectors, knowledge, users

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


@app.middleware("http")
async def attach_flash(request: Request, call_next):
    request.state.error = None
    request.state.success = None
    return await call_next(request)
