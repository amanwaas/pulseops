import os
import secrets
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PulseOps Monitoring Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database Settings (PostgreSQL 16 on Neon)
    # Neon provides a connection string like: postgresql://user:password@ep-xyz-pooler.c-2.postgres.neon.tech/neondb?sslmode=require
    # In asyncpg, standard protocol is: postgresql+asyncpg://...
    DATABASE_URL: str = "sqlite+aiosqlite:///./pulseops.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 300
    DB_POOL_PRE_PING: bool = True

    # Security & Encryption (AES-256-GCM)
    # Master key MUST be 32 bytes (64 hex characters or 44 base64 characters)
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", secrets.token_hex(32))

    # JWT Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24  # 24 hours

    # CORS Settings (Explicitly allowing Vercel production + preview domains)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,https://pulseops-m.vercel.app,https://*.vercel.app"

    @property
    def cors_origins_list(self) -> List[str]:
        val = str(self.CORS_ORIGINS).strip()
        if val.startswith("[") and val.endswith("]"):
            import json
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        return [i.strip() for i in val.split(",") if i.strip()]

    # Health Checking & Alerting Engine Configuration
    HEALTH_CHECK_DEFAULT_INTERVAL_SECONDS: int = 60
    HEALTH_CHECK_DEFAULT_TIMEOUT_SECONDS: int = 5
    CONSECUTIVE_FAILURES_THRESHOLD: int = 3
    LATENCY_SPIKE_THRESHOLD_MS: float = 1500.0  # Alert if avg latency > 1500ms
    RETENTION_DAYS: int = 30

    # Optional Email SMTP Settings
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alerts@pulseops.io"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )


settings = Settings()
