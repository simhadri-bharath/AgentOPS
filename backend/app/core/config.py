"""Application configuration via Pydantic Settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="AgentOps Platform", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    database_url: str = Field(
        default="postgresql+asyncpg://agentops:agentops@localhost:5432/agentops",
        alias="DATABASE_URL",
    )

    gcp_project_id: str = Field(default="", alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="us-central1", alias="GCP_REGION")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    dataset_storage_dir: str = Field(
        default="data/datasets",
        alias="DATASET_STORAGE_DIR",
    )
    evaluation_timeout_seconds: int = Field(
        default=120,
        alias="EVALUATION_TIMEOUT_SECONDS",
    )
    evaluation_max_retries: int = Field(default=2, alias="EVALUATION_MAX_RETRIES")

    redteam_default_judge: str = Field(
        default="gemini-2.5-pro",
        alias="REDTEAM_DEFAULT_JUDGE",
    )
    redteam_use_llm_judge: bool = Field(default=True, alias="REDTEAM_USE_LLM_JUDGE")

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
