from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://job:job@localhost:5437/job"
    internal_service_key: str = "development-only-placeholder"
    employee_service_url: str = "http://employee:8020"
    work_service_url: str = "http://work:8030"
    worker_employee_service_key: str = "development-worker-employee-placeholder"
    worker_work_service_key: str = "development-worker-work-placeholder"
    rabbitmq_url: str = "amqp://job:job@localhost:5672/job"


settings = Settings()
