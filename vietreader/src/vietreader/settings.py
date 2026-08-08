"""Application settings, loaded from environment variables / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIETREADER_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./vietreader.db"

    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_api_key: str = ""
    llm_prompt_version: str = "v1"
    llm_temperature: float = 0.0
    llm_batch_size: int = 40
    llm_max_retries: int = 2

    fetch_user_agent: str = "VietReaderBot/0.1 (personal reading assistant)"
    fetch_timeout_seconds: float = 15.0
    fetch_delay_seconds: float = 1.0
    fetch_max_retries: int = 2

    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
