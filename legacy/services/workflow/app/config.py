from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://workflow:workflow@localhost:5438/workflow"
    internal_service_key: str = "development-workflow-placeholder"
    consumer_service_key: str = "development-consumer-placeholder"
    job_service_url: str = "http://job:8040"
    job_internal_service_key: str = "development-job-placeholder"
    job_workflow_service_key: str = "development-job-workflow-placeholder"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/jobs"


settings = Settings()
