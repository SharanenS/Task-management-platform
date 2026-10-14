from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://employee:employee@localhost:5432/employee"
    internal_service_key: str = "development-only-placeholder"
    app_env: str = "development"
    keycloak_admin_base_url: str = "http://localhost:8080"
    keycloak_realm: str = "taskspace"
    keycloak_admin_client_id: str = "taskspace-employee-admin"
    keycloak_admin_client_secret: str = "development-only-placeholder"


settings = Settings()
