from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno de la aplicación.

    `DATABASE_URL` y `SESSION_SECRET` son obligatorias: si faltan, Pydantic
    falla al iniciar con un mensaje que nombra la variable ausente.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Rumbo AI"
    env: str = "development"
    database_url: str
    groq_api_key: str = ""
    session_secret: str
    api_v1_prefix: str = "/api/v1"
    session_ttl_minutes: int = 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada, fallando claro si falta algo."""
    return Settings()
