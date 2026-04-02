"""app/api/webhook.py — FastAPI webhook (GET verification + POST processing)"""
import hashlib, hmac
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import get_db
from app.services.message_processor import handle_incoming

router = APIRouter()
settings = get_settings()
log = get_logger(__name__)

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        log.info("webhook_verified")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    log.debug("webhook_raw", payload=str(payload)[:400])
    for event in _parse_payload(payload):
        background_tasks.add_task(handle_incoming, event, db)
    return {"status": "ok"}

def _parse_payload(payload: dict) -> list[dict]:
    events = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value    = change.get("value", {})
                contacts = value.get("contacts", [])
                wa_name  = contacts[0]["profile"]["name"] if contacts else ""
                for msg in value.get("messages", []):
                    phone     = msg.get("from", "")
                    wa_msg_id = msg.get("id", "")
                    msg_type  = msg.get("type", "text")
                    if msg_type == "text":
                        user_input = msg.get("text", {}).get("body", "").strip()
                    elif msg_type == "interactive":
                        i = msg.get("interactive", {})
                        itype = i.get("type")
                        user_input = i.get("button_reply" if itype == "button_reply" else "list_reply", {}).get("id", "")
                    elif msg_type == "button":
                        user_input = msg.get("button", {}).get("payload", "")
                    else:
                        user_input = ""
                        log.info("unsupported_msg_type", msg_type=msg_type, phone=phone)
                    if phone:
                        events.append({"phone": phone, "user_input": user_input, "wa_name": wa_name, "wa_message_id": wa_msg_id, "msg_type": msg_type})
    except Exception as exc:
        log.error("payload_parse_error", error=str(exc))
    return events
