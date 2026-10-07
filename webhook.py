from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from config import get_settings
from services.db import init_db, save_call
from services.logging_setup import configure_logging

logger = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.log_level)
init_db(settings.sqlite_path)

app = FastAPI(title="Missed Call AI Receptionist webhooks")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent_id": settings.agent_id}


@app.post("/webhooks/videosdk")
async def videosdk_sip_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """VideoSDK SIP events: call-started, call-answered, call-hangup, ..."""
    if settings.webhook_secret and x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="invalid webhook secret")
    payload = await request.json()
    event = payload.get("event") or payload.get("type") or "unknown"
    call_id = (
        payload.get("id")
        or payload.get("callId")
        or payload.get("roomId")
        or "unknown"
    )
    logger.info(
        "sip_webhook",
        extra={"call_id": str(call_id), "component": event, "metrics": payload},
    )
    if event in {"call-hangup", "call-missed"}:
        save_call(
            settings.sqlite_path,
            {
                "id": f"sip-{call_id}",
                "ended_reason": event,
                "transcript": [{"role": "system", "content": "sip_webhook", "payload": payload}],
            },
        )
    return {"ok": True}
