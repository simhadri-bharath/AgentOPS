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
    # Concurrent agent invocations. A retrieval turn takes ~40s, so serial
    # execution over a 50-sample dataset would exceed half an hour.
    invoke_concurrency: int = Field(default=8, alias="INVOKE_CONCURRENCY")

    judge_model: str = Field(default="gemini-2.5-flash", alias="JUDGE_MODEL")
    judge_temperature: float = Field(default=0.0, alias="JUDGE_TEMPERATURE")
    judge_concurrency: int = Field(default=6, alias="JUDGE_CONCURRENCY")
    # Red-team scans were serial: each attack is an agent round-trip plus judge
    # calls, so a scan against a 40s-per-turn agent took hours.
    redteam_concurrency: int = Field(default=5, alias="REDTEAM_CONCURRENCY")
    # A sample "passes" when its mean judged score clears this. The old rule
    # counted any non-empty response as a pass.
    metric_pass_threshold: float = Field(default=0.7, alias="METRIC_PASS_THRESHOLD")

    # REDTEAM_DEFAULT_JUDGE / REDTEAM_USE_LLM_JUDGE removed: nothing read
    # them. JUDGE_MODEL is the single judge setting, and use_llm_judge is a
    # per-run choice on the scan request.

    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    # Runs left in `running` longer than this after a restart cannot still be
    # in progress: the background task that owned them is gone.
    orphaned_run_timeout_minutes: int = Field(
        default=60, alias="ORPHANED_RUN_TIMEOUT_MINUTES"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        explicit = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if explicit:
            return explicit
        return ["*"] if self.is_development else []

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
