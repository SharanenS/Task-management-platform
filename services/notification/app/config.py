from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://notification:notification@localhost:5439/notification"
    internal_service_key: str = "development-notification-placeholder"
    consumer_service_key: str = "development-notification-consumer-placeholder"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/jobs"


settings = Settings()
