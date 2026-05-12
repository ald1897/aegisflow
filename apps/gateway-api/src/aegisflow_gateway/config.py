from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "gateway-api"
    environment: str = "local"
    api_title: str = "AegisFlow Gateway API"
    api_version: str = "0.1.0"
    database_url: str = Field(
        default="postgresql+asyncpg://aegisflow:aegisflow@localhost:5432/aegisflow",
        validation_alias="DATABASE_URL",
    )
    temporal_address: str = Field(default="localhost:7233", validation_alias="TEMPORAL_ADDRESS")
    temporal_task_queue: str = Field(default="aegisflow-workflows", validation_alias="TEMPORAL_TASK_QUEUE")
    enable_temporal_start: bool = Field(default=False, validation_alias="ENABLE_TEMPORAL_START")
    kafka_bootstrap_servers: str = Field(default="localhost:19092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_workflow_events_topic: str = Field(default="workflow-events", validation_alias="KAFKA_WORKFLOW_EVENTS_TOPIC")
    enable_event_publishing: bool = Field(default=False, validation_alias="ENABLE_EVENT_PUBLISHING")
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    log_level: str = "INFO"
    enable_telemetry: bool = Field(default=False, validation_alias="ENABLE_TELEMETRY")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4318",
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
