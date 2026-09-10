"""Application configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Enterprise Task Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str

    # Message Broker (RabbitMQ / Celery)
    RABBITMQ_URL: str

    # Keycloak Authentication
    KEYCLOAK_SERVER_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str

    # Outbox Publisher
    OUTBOX_PUBLISHER_BATCH_SIZE: int = Field(default=50, gt=0)
    OUTBOX_PUBLISHER_POLL_INTERVAL_SECONDS: float = Field(default=1.0, gt=0.0)
    OUTBOX_PUBLISHER_LEASE_SECONDS: int = Field(default=30, gt=0)

    @property
    def keycloak_issuer(self) -> str:
        """Construct the expected issuer URL for JWT validation."""
        server = self.KEYCLOAK_SERVER_URL.rstrip('/')
        return f"{server}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_jwks_url(self) -> str:
        """Construct the JWKS discovery URL."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    model_config = {"env_file": [".env", "../.env"], "case_sensitive": True, "extra": "ignore"}


settings = Settings()
