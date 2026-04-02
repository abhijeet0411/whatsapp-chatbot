"""app/services/message_processor.py — orchestrates the full pipeline"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.db.models import MessageLog, User
from app.services import session_manager as sm
from app.services.complaint_service import save_complaint
from app.services.flow_engine import FlowEngine
from app.services.whatsapp_sender import send_message

log = get_logger(__name__)
_engine = FlowEngine()

async def handle_incoming(event: dict, db: AsyncSession) -> None:
    phone      = event["phone"]
    user_input = event["user_input"]
    wa_name    = event.get("wa_name", "")
    wa_msg_id  = event.get("wa_message_id", "")
    msg_type   = event.get("msg_type", "text")

    log.info("incoming", phone=phone, input=user_input[:60], type=msg_type)

    user = await _upsert_user(phone, wa_name, db)
    sess = await sm.get_session(phone, db)

    await _log_message(db, wa_msg_id, user.id, phone, "in", msg_type, {"text": user_input}, sess["current_node"])

    next_node, reply_payload = _engine.process(sess, user_input, wa_name)
    sess["current_node"] = next_node

    if next_node == "COMPLAINT_SUCCESS":
        try:
            await save_complaint(db, sess, phone)
        except Exception as exc:
            log.error("complaint_save_error", error=str(exc), phone=phone)

    await sm.save_session(phone, sess, db)
    await send_message(phone, reply_payload)
    await _log_message(db, None, user.id, phone, "out", reply_payload.get("type","text"), reply_payload, next_node)

async def _upsert_user(phone: str, wa_name: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        user = User(phone=phone, name=wa_name or None, language="mr")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        log.info("new_user", phone=phone, name=wa_name)
    elif wa_name and user.name != wa_name:
        user.name = wa_name
        await db.commit()
    return user

async def _log_message(db, wa_message_id, user_id, phone, direction, message_type, content, node):
    entry = MessageLog(wa_message_id=wa_message_id, user_id=user_id, phone=phone,
                       direction=direction, message_type=message_type, content=content, node_at_time=node)
    db.add(entry)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
