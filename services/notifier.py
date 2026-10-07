from __future__ import annotations
import logging
from typing import Any
import httpx
from config import Settings

logger = logging.getLogger(__name__)


def format_summary(summary: dict[str, Any], *, urgent: bool = False) -> str:
    prefix = "URGENT missed call" if urgent else "Missed-call summary"
    lines = [
        f"{prefix} (call {summary.get('id')})",
        f"Caller: {summary.get('caller') or 'unknown'}",
        f"Reason: {summary.get('reason') or 'n/a'}",
        f"Urgency: {summary.get('urgency') or 'n/a'}",
        f"Callback: {summary.get('callback') or 'n/a'}",
        f"Duration: {summary.get('duration_seconds')}s",
    ]
    if summary.get("ended_reason"):
        lines.append(f"Ended: {summary['ended_reason']}")
    return "\n".join(lines)


async def send_telegram(settings: Settings, text: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("telegram_not_configured")
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
            },
        )
        response.raise_for_status()


async def send_whatsapp(settings: Settings, text: str) -> None:
    if not (
        settings.whatsapp_token
        and settings.whatsapp_phone_number_id
        and settings.whatsapp_to
    ):
        logger.warning("whatsapp_not_configured")
        return
    url = (
        "https://graph.facebook.com/v21.0/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": settings.whatsapp_to,
                "type": "text",
                "text": {"body": text[:4096]},
            },
        )
        response.raise_for_status()


async def notify(
    settings: Settings,
    summary: dict[str, Any],
    *,
    urgent: bool = False,
) -> None:
    text = format_summary(summary, urgent=urgent)
    channel = settings.notify_channel
    errors: list[str] = []
    if channel in ("telegram", "both"):
        try:
            await send_telegram(settings, text)
        except Exception as exc:  # noqa: BLE001 — still try WhatsApp / log
            errors.append(f"telegram: {exc}")
    if channel in ("whatsapp", "both"):
        try:
            await send_whatsapp(settings, text)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"whatsapp: {exc}")
    if errors:
        logger.error(
            "notify_failed",
            extra={"call_id": summary.get("id"), "errors": errors},
        )
    else:
        logger.info(
            "notify_sent",
            extra={"call_id": summary.get("id"), "urgent": urgent},
        )
