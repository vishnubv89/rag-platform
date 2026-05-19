"""
Notification action tools — send messages to Slack and Microsoft Teams.
"""
import httpx

from rag_chatbot.config import settings
from rag_chatbot.agent.actions.registry import ActionResult, register_action


@register_action("slack_send_message")
async def send_slack_message(params: dict, state) -> ActionResult:
    """
    Send a message to a Slack channel.
    params: {channel, text, thread_ts? (optional, for threading)}
    """
    token = settings.slack_bot_token
    if not token:
        return ActionResult(success=False, message="Slack bot token not configured.")

    channel = params.get("channel", "")
    text = params.get("text", "")
    if not channel or not text:
        return ActionResult(success=False, message="channel and text are required.")

    payload: dict = {"channel": channel, "text": text}
    if params.get("thread_ts"):
        payload["thread_ts"] = params["thread_ts"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
        data = r.json()
        if not data.get("ok"):
            return ActionResult(success=False, message=f"Slack error: {data.get('error', 'unknown')}")
        return ActionResult(
            success=True,
            message=f"Message sent to {channel}.",
            data={"ts": data.get("ts"), "channel": data.get("channel")},
        )
    except Exception as e:
        return ActionResult(success=False, message=f"Failed to send Slack message: {e}")


@register_action("teams_send_message")
async def send_teams_message(params: dict, state) -> ActionResult:
    """
    Send a message to a Microsoft Teams channel via incoming webhook.
    params: {webhook_url, text, title?}
    """
    webhook_url = params.get("webhook_url", "")
    text = params.get("text", "")
    if not webhook_url or not text:
        return ActionResult(success=False, message="webhook_url and text are required.")

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "0076D7",
        "summary": params.get("title", "RAG Agent Notification"),
        "sections": [{"activityTitle": params.get("title", "Notification"), "activityText": text}],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=payload)
            r.raise_for_status()
        return ActionResult(success=True, message="Teams message sent.", data={})
    except Exception as e:
        return ActionResult(success=False, message=f"Failed to send Teams message: {e}")
