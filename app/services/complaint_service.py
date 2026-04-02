"""app/services/complaint_service.py — complaint persistence"""
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.db.models import Complaint, User

log = get_logger(__name__)

async def save_complaint(db: AsyncSession, sess: dict, phone: str) -> str:
    ctx = sess.get("context", {})
    lang = sess.get("language", "mr")

    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User not found: {phone}")

    cid_result = await db.execute(text("SELECT generate_complaint_id()"))
    complaint_id = cid_result.scalar()

    complaint = Complaint(
        complaint_id=complaint_id,
        user_id=user.id,
        phone=phone,
        ward=ctx.get("ward"),
        ward_name=ctx.get("ward_name"),
        department=ctx.get("department"),
        dept_name=ctx.get("dept_name"),
        complaint_type=ctx.get("complaint_type"),
        complaint_text=ctx.get("complaint_text", ""),
        status="open",
        officer_name=ctx.get("officer_name",""),
        officer_phone=ctx.get("officer_phone",""),
        language=lang,
        metadata_={"session_context": ctx},
    )
    db.add(complaint)
    await db.commit()

    ctx["complaint_id"] = complaint_id
    ctx["date"] = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    sess["context"] = ctx

    log.info("complaint_saved", complaint_id=complaint_id, phone=phone)
    return complaint_id

async def get_complaint_status(db: AsyncSession, complaint_id: str) -> dict | None:
    result = await db.execute(select(Complaint).where(Complaint.complaint_id == complaint_id))
    c = result.scalar_one_or_none()
    if not c:
        return None
    return {"complaint_id":c.complaint_id,"status":c.status,"ward_name":c.ward_name,"dept_name":c.dept_name,"complaint_text":c.complaint_text,"officer_name":c.officer_name,"officer_phone":c.officer_phone,"created_at":c.created_at.isoformat() if c.created_at else None}
