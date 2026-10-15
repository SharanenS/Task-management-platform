from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    oidc_issuer: str = "http://localhost:8080/realms/taskspace"
    oidc_jwks_url: str = "http://localhost:8080/realms/taskspace/protocol/openid-connect/certs"
    oidc_audience: str = "taskspace-web"
    employee_service_url: str = "http://127.0.0.1:8020"
    work_service_url: str = "http://127.0.0.1:8030"
    internal_service_key: str = "development-only-placeholder"
    work_internal_service_key: str = "development-only-placeholder"


settings = Settings()
