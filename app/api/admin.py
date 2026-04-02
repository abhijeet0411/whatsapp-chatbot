"""app/api/admin.py — lightweight admin endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import get_db, Complaint, User
from app.services.complaint_service import get_complaint_status

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/complaints/{complaint_id}")
async def complaint_detail(complaint_id: str, db: AsyncSession = Depends(get_db)):
    data = await get_complaint_status(db, complaint_id)
    if not data:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return data

@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    users_count      = (await db.execute(select(func.count()).select_from(User))).scalar()
    complaints_count = (await db.execute(select(func.count()).select_from(Complaint))).scalar()
    open_count       = (await db.execute(select(func.count()).select_from(Complaint).where(Complaint.status == "open"))).scalar()
    return {"total_users": users_count, "total_complaints": complaints_count, "open_complaints": open_count}

@router.patch("/complaints/{complaint_id}/status")
async def update_status(complaint_id: str, status: str, db: AsyncSession = Depends(get_db)):
    valid = {"open","acknowledged","in_progress","resolved","closed"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    result = await db.execute(select(Complaint).where(Complaint.complaint_id == complaint_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    c.status = status
    await db.commit()
    return {"complaint_id": complaint_id, "status": status}
