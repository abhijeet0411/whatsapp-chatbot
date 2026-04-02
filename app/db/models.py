"""app/db/models.py — SQLAlchemy async ORM models"""
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=(settings.app_env == "development"),
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True)
    phone      = Column(String(20), nullable=False, unique=True, index=True)
    name       = Column(String(120))
    language   = Column(String(2), nullable=False, default="mr")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_blocked = Column(Boolean, nullable=False, default=False)
    metadata_  = Column("metadata", JSONB, nullable=False, default=dict)

    sessions   = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    current_node   = Column(String(80), nullable=False, default="START")
    previous_node  = Column(String(80))
    language       = Column(String(2), nullable=False, default="mr")
    context        = Column(JSONB, nullable=False, default=dict)
    is_active      = Column(Boolean, nullable=False, default=True)
    fallback_count = Column(SmallInteger, nullable=False, default=0)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at     = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="sessions")


class Complaint(Base):
    __tablename__ = "complaints"

    id             = Column(Integer, primary_key=True)
    complaint_id   = Column(String(20), nullable=False, unique=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    phone          = Column(String(20), nullable=False)
    ward           = Column(String(40))
    ward_name      = Column(String(120))
    department     = Column(String(40))
    dept_name      = Column(String(120))
    complaint_type = Column(String(80))
    complaint_text = Column(Text, nullable=False)
    status         = Column(String(20), nullable=False, default="open")
    officer_name   = Column(String(120))
    officer_phone  = Column(String(20))
    language       = Column(String(2), nullable=False, default="mr")
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at    = Column(DateTime(timezone=True))
    metadata_      = Column("metadata", JSONB, nullable=False, default=dict)

    user = relationship("User", back_populates="complaints")


class MessageLog(Base):
    __tablename__ = "messages_log"

    id            = Column(BigInteger, primary_key=True)
    wa_message_id = Column(String(80), unique=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    phone         = Column(String(20), nullable=False)
    direction     = Column(String(4), nullable=False)   # in | out
    message_type  = Column(String(20), nullable=False)
    content       = Column(JSONB, nullable=False, default=dict)
    node_at_time  = Column(String(80))
    status        = Column(String(20), default="received")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
