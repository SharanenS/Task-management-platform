from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://work:work@localhost:5436/work"
    internal_service_key: str = "development-only-placeholder"
    job_worker_service_key: str = "development-job-worker-placeholder"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/jobs"


settings = Settings()
