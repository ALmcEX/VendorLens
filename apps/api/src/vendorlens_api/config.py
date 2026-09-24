from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VENDORLENS_",
        extra="forbid",
    )

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    dependency_timeout_seconds: float = Field(default=2.0, ge=0.1, le=10.0)
