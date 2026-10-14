from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://employee:employee@localhost:5432/employee"
    internal_service_key: str = "development-only-placeholder"
    app_env: str = "development"


settings = Settings()
