from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from admin_ui import client

router = APIRouter()


@router.get("/documents")
async def list_documents(request: Request, page: int = 1):
    org_id = request.state.active_org_id
    try:
        docs = await client.list_docs(org_id=org_id, page=page)
        orgs = await client.list_orgs()
    except Exception as e:
        docs, orgs = {"items": [], "total": 0}, []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "documents.html",
        {
            "docs": docs,
            "orgs": orgs,
            "active_org_id": org_id,
            "page": page,
            "active_page": "documents",
        },
    )


@router.get("/documents/{doc_id}")
async def document_detail(request: Request, doc_id: int, refresh: int = 0):
    org_id = request.state.active_org_id
    try:
        doc = await client.get_doc(doc_id)
    except Exception as e:
        doc = {}
        request.state.error = str(e)

    try:
        topics_data = await client.get_doc_topics(doc_id, refresh=bool(refresh))
        topics = topics_data.get("topics", [])
    except Exception:
        topics = []

    cfg: dict = {}
    permissions: list = []
    try:
        cfg_resp = await client.get_config(org_id=org_id)
        cfg = cfg_resp.get("config", {})
        if cfg.get("feature_doc_acls") == "true":
            permissions = await client.get_doc_permissions(doc_id)
    except Exception:
        pass

    all_users: list = []
    try:
        if cfg.get("feature_doc_acls") == "true":
            all_users = await client.list_users(org_id=org_id)
    except Exception:
        pass

    return request.app.state.templates.TemplateResponse(
        request,
        "document_detail.html",
        {
            "doc": doc,
            "topics": topics,
            "active_page": "documents",
            "config": cfg,
            "permissions": permissions,
            "all_users": all_users,
        },
    )


@router.post("/documents/{doc_id}/restrict")
async def toggle_doc_restricted(doc_id: int, is_restricted: str = Form("false")):
    await client.set_doc_restricted(doc_id, is_restricted == "true")
    return RedirectResponse(f"/documents/{doc_id}?saved=1", status_code=303)


@router.post("/documents/{doc_id}/permissions/grant")
async def grant_permission(doc_id: int, user_id: str = Form(...)):
    await client.grant_doc_permission(doc_id, int(user_id))
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/permissions/{user_id}/revoke")
async def revoke_permission(doc_id: int, user_id: int):
    await client.revoke_doc_permission(doc_id, user_id)
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/delete")
async def delete_document(doc_id: int, org_id: str | None = Form(None)):
    org_id = int(org_id) if org_id else None
    await client.delete_doc(doc_id, org_id=org_id)
    return RedirectResponse("/documents", status_code=303)


@router.post("/documents/ingest-file")
async def ingest_file_document(
    file: UploadFile = File(...),
    org_id: str | None = Form(None),
):
    org_id_int = int(org_id) if org_id else None
    content = await file.read()
    await client.ingest_file_upload(filename=file.filename or "upload", content=content, org_id=org_id_int)
    return RedirectResponse("/documents", status_code=303)


@router.post("/documents/ingest")
async def ingest_document(
    title: str = Form(...),
    text: str = Form(...),
    source: str = Form(""),
    org_id: str | None = Form(None),
):
    org_id_int = int(org_id) if org_id else None
    await client.ingest_text(title=title, text=text, source=source, org_id=org_id_int)
    return RedirectResponse("/documents", status_code=303)
