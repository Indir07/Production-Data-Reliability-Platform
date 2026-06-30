import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Production Data Reliability Platform"
    app_version: str = "0.1.0"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pdrp:pdrp_secret@localhost:5432/pdrp"
    )

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production-please")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Alerting
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    pagerduty_routing_key: str = os.getenv("PAGERDUTY_ROUTING_KEY", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")

    # OpenLineage
    openlineage_url: str = os.getenv("OPENLINEAGE_URL", "http://localhost:5000")
    openlineage_namespace: str = os.getenv("OPENLINEAGE_NAMESPACE", "pdrp")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
