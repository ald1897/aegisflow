from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "agent-runtime"
    environment: str = "local"
    log_level: str = "INFO"
    prompts_path: Path = Field(default=Path("prompts"), validation_alias="PROMPTS_PATH")
    tool_runtime_url: str = Field(default="http://localhost:8020", validation_alias="TOOL_RUNTIME_URL")
    enable_tool_runtime: bool = Field(default=False, validation_alias="ENABLE_TOOL_RUNTIME")
    enable_telemetry: bool = Field(default=False, validation_alias="ENABLE_TELEMETRY")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4318",
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
