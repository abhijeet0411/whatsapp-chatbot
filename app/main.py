"""app/main.py — FastAPI application entry point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.api.webhook import router as webhook_router
from app.api.admin import router as admin_router

settings = get_settings()
setup_logging()
log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", env=settings.app_env, municipality=settings.municipality_name)
    yield
    log.info("shutdown")

app = FastAPI(
    title="Municipal WhatsApp Chatbot",
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(admin_router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.municipality_name}
