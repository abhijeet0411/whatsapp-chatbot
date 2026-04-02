"""app/services/whatsapp_sender.py — WhatsApp Cloud API sender"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)

def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_message(to: str, payload: dict) -> dict:
    msg_type = payload.get("type", "text")
    if msg_type == "text":
        body = {"messaging_product":"whatsapp","recipient_type":"individual","to":to,"type":"text","text":{"body":payload["body"],"preview_url":False}}
    elif msg_type == "interactive":
        body = {"messaging_product":"whatsapp","recipient_type":"individual","to":to,"type":"interactive","interactive":payload["interactive"]}
    else:
        body = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":str(payload)}}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(settings.whatsapp_api_url, json=body, headers=_headers())

    if resp.status_code != 200:
        log.error("whatsapp_send_failed", status=resp.status_code, body=resp.text[:500], to=to)
        resp.raise_for_status()

    result = resp.json()
    log.info("whatsapp_sent", to=to, msg_type=msg_type, wa_id=result.get("messages",[{}])[0].get("id"))
    return result

async def send_text(to: str, text: str) -> dict:
    return await send_message(to, {"type": "text", "body": text})
