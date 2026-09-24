from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VENDORLENS_",
        extra="forbid",
    )

    database_url: str = Field(min_length=1)
    queue_name: str = "example_jobs"
    visibility_timeout_seconds: int = Field(default=30, ge=5, le=300)
    max_attempts: int = Field(default=3, ge=1, le=10)
    poll_interval_seconds: float = Field(default=1.0, ge=0.05, le=30.0)
    shutdown_grace_seconds: float = Field(default=20.0, ge=0.1, le=60.0)
