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
    try:
        doc = await client.get_doc(doc_id)
    except Exception as e:
        doc = {}
        request.state.error = str(e)

    # Topics are fetched lazily — if not yet cached this triggers LLM extraction.
    # Pass refresh=True when the user clicked "Refresh topics".
    # On error (e.g. no chunks yet) we just show an empty state.
    try:
        topics_data = await client.get_doc_topics(doc_id, refresh=bool(refresh))
        topics = topics_data.get("topics", [])
    except Exception:
        topics = []

    return request.app.state.templates.TemplateResponse(
        request,
        "document_detail.html",
        {"doc": doc, "topics": topics, "active_page": "documents"},
    )


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
