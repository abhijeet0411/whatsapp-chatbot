"""app/services/session_manager.py
Redis-backed session manager with PostgreSQL persistence.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Session, User

settings = get_settings()
log = get_logger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _key(phone: str) -> str:
    return f"session:{phone}"


async def get_session(phone: str, db: AsyncSession) -> dict:
    """Return active session dict, creating one if needed."""
    redis = await get_redis()
    raw = await redis.get(_key(phone))
    if raw:
        return json.loads(raw)

    result = await db.execute(
        select(Session)
        .join(User, User.id == Session.user_id)
        .where(User.phone == phone, Session.is_active == True)
        .order_by(Session.created_at.desc())
        .limit(1)
    )
    db_session = result.scalar_one_or_none()

    if db_session and db_session.expires_at > datetime.now(timezone.utc):
        sess = _to_dict(db_session)
        await _cache(phone, sess)
        return sess

    return await create_session(phone, db)


async def create_session(phone: str, db: AsyncSession) -> dict:
    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()

    if user:
        await db.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.is_active == True)
            .values(is_active=False)
        )
        await db.commit()

        expires = datetime.now(timezone.utc) + timedelta(seconds=settings.session_ttl_seconds)
        db_sess = Session(
            user_id=user.id,
            current_node="START",
            language=user.language,
            context={},
            is_active=True,
            fallback_count=0,
            expires_at=expires,
        )
        db.add(db_sess)
        await db.commit()
        await db.refresh(db_sess)
        sess = _to_dict(db_sess)
    else:
        sess = {
            "phone": phone,
            "current_node": "START",
            "previous_node": None,
            "language": "mr",
            "context": {},
            "fallback_count": 0,
            "db_id": None,
        }

    await _cache(phone, sess)
    return sess


async def save_session(phone: str, sess: dict, db: AsyncSession) -> None:
    await _cache(phone, sess)
    if sess.get("db_id"):
        await db.execute(
            update(Session)
            .where(Session.id == sess["db_id"])
            .values(
                current_node=sess["current_node"],
                previous_node=sess.get("previous_node"),
                language=sess["language"],
                context=sess["context"],
                fallback_count=sess.get("fallback_count", 0),
            )
        )
        await db.commit()


async def clear_session(phone: str, db: AsyncSession) -> None:
    redis = await get_redis()
    await redis.delete(_key(phone))

    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()
    if user:
        await db.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.is_active == True)
            .values(is_active=False)
        )
        await db.commit()


async def _cache(phone: str, sess: dict) -> None:
    redis = await get_redis()
    await redis.setex(_key(phone), settings.session_ttl_seconds, json.dumps(sess, default=str))


def _to_dict(s: Session) -> dict:
    return {
        "db_id": s.id,
        "current_node": s.current_node,
        "previous_node": s.previous_node,
        "language": s.language,
        "context": s.context or {},
        "fallback_count": s.fallback_count,
    }
