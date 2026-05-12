from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "evaluation-service"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+asyncpg://aegisflow:aegisflow@localhost:5432/aegisflow",
        validation_alias="DATABASE_URL",
    )
    metrics_port: int = Field(default=8040, validation_alias="METRICS_PORT")
    enable_telemetry: bool = Field(default=False, validation_alias="ENABLE_TELEMETRY")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4318",
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    enable_external_judge_model: bool = Field(default=False, validation_alias="ENABLE_EXTERNAL_JUDGE_MODEL")
    external_judge_model_provider: str = Field(default="disabled", validation_alias="EXTERNAL_JUDGE_MODEL_PROVIDER")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
