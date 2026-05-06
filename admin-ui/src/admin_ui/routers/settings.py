from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from admin_ui import client

router = APIRouter()

CONFIG_KEYS = [
    "llm_provider", "llm_model",
    "anthropic_model", "anthropic_api_key",
    "embedding_model", "embedding_dim",
    "retrieval_top_k", "grader_max_loops",
    "chunk_size", "chunk_overlap",
]


@router.get("/settings")
async def settings_page(request: Request, org_id: int | None = None):
    try:
        cfg = await client.get_config(org_id=org_id)
        orgs = await client.list_orgs()
    except Exception as e:
        cfg, orgs = {"config": {}}, []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        {
            "config": cfg.get("config", {}),
            "config_keys": CONFIG_KEYS,
            "orgs": orgs,
            "active_org_id": org_id,
            "active_page": "settings",
        },
    )


@router.post("/settings")
async def save_settings(
    request: Request,
    org_id: int | None = Form(None),
    llm_provider: str = Form("gemini"),
    llm_model: str = Form(""),
    anthropic_model: str = Form(""),
    anthropic_api_key: str = Form(""),
    embedding_model: str = Form(""),
    embedding_dim: str = Form(""),
    retrieval_top_k: str = Form(""),
    grader_max_loops: str = Form(""),
    chunk_size: str = Form(""),
    chunk_overlap: str = Form(""),
):
    new_cfg: dict[str, str] = {
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "anthropic_model": anthropic_model,
        "embedding_model": embedding_model,
        "embedding_dim": embedding_dim,
        "retrieval_top_k": retrieval_top_k,
        "grader_max_loops": grader_max_loops,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    # Only update anthropic_api_key if a new value was submitted
    if anthropic_api_key:
        new_cfg["anthropic_api_key"] = anthropic_api_key

    await client.update_config(
        org_id=org_id, cfg={k: v for k, v in new_cfg.items() if v}
    )
    redirect = f"/settings?org_id={org_id}&saved=1" if org_id else "/settings?saved=1"
    return RedirectResponse(redirect, status_code=303)
