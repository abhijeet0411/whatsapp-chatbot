"""app/core/config.py — centralised settings via pydantic-settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # WhatsApp
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = "CHANGE_ME"
    whatsapp_api_version: str = "v19.0"

    @property
    def whatsapp_api_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self.whatsapp_api_version}"
            f"/{self.whatsapp_phone_number_id}/messages"
        )

    # Database
    database_url: str = "postgresql+asyncpg://botuser:botpass@localhost:5432/ampbot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 86400  # 24 h

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    max_fallback_retries: int = 3
    flow_file: str = "flows/flow.json"

    # Municipality
    municipality_name: str = "Ahilyanagar Mahanagar Palika"
    municipality_phone: str = "02412345678"


@lru_cache
def get_settings() -> Settings:
    return Settings()
