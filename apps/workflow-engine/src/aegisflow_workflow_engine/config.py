from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "workflow-engine"
    environment: str = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://aegisflow:aegisflow@localhost:5432/aegisflow",
        validation_alias="DATABASE_URL",
    )
    temporal_address: str = Field(default="localhost:7233", validation_alias="TEMPORAL_ADDRESS")
    temporal_task_queue: str = Field(default="aegisflow-workflows", validation_alias="TEMPORAL_TASK_QUEUE")
    kafka_bootstrap_servers: str = Field(default="localhost:19092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_workflow_events_topic: str = Field(default="workflow-events", validation_alias="KAFKA_WORKFLOW_EVENTS_TOPIC")
    enable_event_publishing: bool = Field(default=True, validation_alias="ENABLE_EVENT_PUBLISHING")
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
