from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://class_catchup:class_catchup@localhost:5432/class_catchup"
    )
    app_environment: str = "development"
    cookie_secure: bool = False
    session_hours: int = 12
    default_timezone: str = "Africa/Lagos"
    material_storage_root: str = "materials-private"
    material_max_bytes: int = 20 * 1024 * 1024
    aws_region: str | None = None
    bedrock_model_id: str | None = None
    provider_read_timeout_seconds: int = 60
    agent_max_turns: int = 8
    agent_max_total_tokens: int = 12000


@lru_cache
def get_settings() -> Settings:
    return Settings()
