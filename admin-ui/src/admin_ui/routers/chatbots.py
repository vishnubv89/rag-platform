from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from admin_ui import client

router = APIRouter()


@router.get("/chatbots")
async def list_chatbots(request: Request):
    org_id = request.state.active_org_id
    chatbots: list = []
    orgs: list = []
    new_key: str | None = request.query_params.get("new_key")
    new_chatbot_id: str | None = request.query_params.get("new_chatbot_id")
    try:
        orgs = await client.list_orgs()
        if org_id:
            chatbots = await client.list_chatbots(org_id)
    except Exception as e:
        request.state.error = str(e)

    return request.app.state.templates.TemplateResponse(
        request,
        "chatbots.html",
        {
            "chatbots": chatbots,
            "orgs": orgs,
            "active_org_id": org_id,
            "active_page": "chatbots",
            "new_key": new_key,
            "new_chatbot_id": new_chatbot_id,
        },
    )


@router.post("/chatbots")
async def create_chatbot(
    request: Request,
    org_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    system_instruction: str = Form(""),
    welcome_message: str = Form(""),
):
    org_id_int = int(org_id)
    result = await client.create_chatbot(
        org_id=org_id_int,
        name=name,
        description=description,
        system_instruction=system_instruction,
        welcome_message=welcome_message,
    )
    raw_key = result.get("key", "")
    chatbot_id = result.get("id", "")
    return RedirectResponse(
        f"/chatbots?new_key={raw_key}&new_chatbot_id={chatbot_id}",
        status_code=303,
    )


@router.post("/chatbots/{chatbot_id}/toggle")
async def toggle_chatbot(request: Request, chatbot_id: int, is_active: str = Form("true")):
    org_id = request.state.active_org_id
    await client.patch_chatbot(org_id, chatbot_id, is_active=(is_active == "true"))
    return RedirectResponse("/chatbots", status_code=303)


@router.post("/chatbots/{chatbot_id}/update")
async def update_chatbot(
    request: Request,
    chatbot_id: int,
    name: str = Form(...),
    description: str = Form(""),
    system_instruction: str = Form(""),
    welcome_message: str = Form(""),
):
    org_id = request.state.active_org_id
    await client.patch_chatbot(
        org_id, chatbot_id,
        name=name,
        description=description,
        system_instruction=system_instruction,
        welcome_message=welcome_message,
    )
    return RedirectResponse("/chatbots?saved=1", status_code=303)


@router.post("/chatbots/{chatbot_id}/delete")
async def delete_chatbot(request: Request, chatbot_id: int):
    org_id = request.state.active_org_id
    await client.delete_chatbot(org_id, chatbot_id)
    return RedirectResponse("/chatbots", status_code=303)
