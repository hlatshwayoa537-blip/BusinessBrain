from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "VEXION API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://businessbrain:businessbrain@localhost:5432/businessbrain"
    jwt_secret_key: str = "development-only-change-me"
    access_token_expire_minutes: int = 30
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_upload_url_expire_seconds: int = 300
    s3_download_url_expire_seconds: int = 60
    quarantine_upload_ttl_hours: int = 24
    clamav_host: str = ""
    clamav_port: int = 3310
    clamav_timeout_seconds: int = 60
    frontend_base_url: str = "http://localhost:5173"
    api_base_url: str = "https://businessbrain-api.onrender.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    payfast_merchant_id: str = ""
    payfast_merchant_key: str = ""
    payfast_passphrase: str = ""
    payfast_sandbox: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql+psycopg2://"):
            return value.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def public_frontend_base_url(self) -> str:
        configured = self.frontend_base_url.strip().rstrip("/")
        if self.app_env.lower() == "production" and not configured.startswith("https://"):
            return next((origin.rstrip("/") for origin in self.cors_origins if origin.startswith("https://")), "")
        return configured


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
