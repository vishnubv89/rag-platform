from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from admin_ui import client

router = APIRouter()


@router.get("/documents")
async def list_documents(request: Request, org_id: int | None = None, page: int = 1):
    try:
        docs = await client.list_docs(org_id=org_id, page=page)
        orgs = await client.list_orgs()
    except Exception as e:
        docs, orgs = {"items": [], "total": 0}, []
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        "documents.html",
        {
            "request": request,
            "docs": docs,
            "orgs": orgs,
            "active_org_id": org_id,
            "page": page,
            "active_page": "documents",
        },
    )


@router.get("/documents/{doc_id}")
async def document_detail(request: Request, doc_id: int):
    try:
        doc = await client.get_doc(doc_id)
    except Exception as e:
        doc = {}
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        "document_detail.html",
        {"request": request, "doc": doc, "active_page": "documents"},
    )


@router.post("/documents/{doc_id}/delete")
async def delete_document(doc_id: int, org_id: int | None = None):
    await client.delete_doc(doc_id)
    redirect = f"/documents?org_id={org_id}" if org_id else "/documents"
    return RedirectResponse(redirect, status_code=303)


@router.post("/documents/ingest")
async def ingest_document(
    title: str = Form(...),
    text: str = Form(...),
    source: str = Form(""),
    org_id: int | None = Form(None),
):
    await client.ingest_text(title=title, text=text, source=source, org_id=org_id)
    redirect = f"/documents?org_id={org_id}" if org_id else "/documents"
    return RedirectResponse(redirect, status_code=303)
