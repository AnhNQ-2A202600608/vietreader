"""Application settings, loaded from environment variables / .env."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIETREADER_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./vietreader.db"
    # Local/test can create tables for convenience. Production must run Alembic explicitly.
    auto_create_schema: bool = True
    # Fail closed on hosts with ephemeral disks instead of silently falling back to SQLite.
    require_postgres: bool = False

    # Tên người đọc, dùng cho lời chào và các trạng thái rỗng.
    # Đổi bằng VIETREADER_READER_NAME trong .env.
    reader_name: str = "Ngân Giang"

    llm_provider: Literal["anthropic"] = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_api_key: str = ""
    llm_prompt_version: str = "v1"
    llm_temperature: float = 0.0
    llm_batch_size: int = 40
    llm_max_retries: int = 2

    fetch_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    fetch_timeout_seconds: float = 15.0
    fetch_delay_seconds: float = 1.0
    fetch_max_retries: int = 2
    fetch_verify_tls: bool = True
    fetch_allow_private_networks: bool = False

    # Local development stays frictionless. Public deployments should set
    # REQUIRE_AUTH=1 plus both credentials (render.yaml does this).
    require_auth: bool = False
    auth_username: str = ""
    auth_password: str = ""

    log_level: str = "INFO"

    @model_validator(mode="after")
    def _validate_deployment(self) -> Settings:
        has_username = bool(self.auth_username)
        has_password = bool(self.auth_password)
        if has_username != has_password:
            raise ValueError("both auth_username and auth_password must be set together")
        if self.require_auth and not (has_username and has_password):
            raise ValueError(
                "require_auth is enabled but VIETREADER_AUTH_USERNAME/PASSWORD are missing"
            )
        if self.require_postgres and not self.database_url.startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        ):
            raise ValueError(
                "require_postgres is enabled but VIETREADER_DATABASE_URL is not PostgreSQL"
            )
        return self


def get_settings() -> Settings:
    return Settings()
