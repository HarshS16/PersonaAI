"""Application settings, loaded from environment / .env.

A single `settings` instance is imported across the app. Secrets never have
real defaults so that a misconfigured production deploy fails loudly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://persona:persona@localhost:5432/persona"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Security
    jwt_secret: str = "change-me-in-production"
    encryption_key: str = "change-me-32-byte-urlsafe-base64="
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    # AI
    llm_provider: str = "fake"
    llm_model_fast: str = "claude-haiku-4-5-20251001"
    llm_model_strong: str = "claude-opus-4-8"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    voyage_api_key: str = ""

    # OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:3000/api/backend/auth/github/callback"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/api/backend/auth/google/callback"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@personaai.local"

    # Storage
    storage_backend: str = "local"
    storage_local_dir: str = "./data/uploads"

    # Observability
    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    sync_database_url: str = Field(default="", exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def alembic_url(self) -> str:
        """Alembic runs migrations synchronously via the psycopg (v3) driver."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
