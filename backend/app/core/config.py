import re
from urllib.parse import unquote, urlsplit
"""Application configuration via environment variables."""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


INSECURE_SECRET_MARKERS = [
    "insecure",
    "changeme",
    "change-in-production",
    "your_development_secret_key",
    "your_postgres_password",
    "your_rabbitmq_password",
    "your_client_secret",
]


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Enterprise Task Platform"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Security & Authentication Secrets
    SECRET_KEY: str = Field(default="insecure-dev-secret-key-change-in-production-min-32-chars")
    KEYCLOAK_CLIENT_SECRET: str = Field(default="")

    # Database
    DATABASE_URL: str

    # Message Broker (RabbitMQ / Celery)
    RABBITMQ_URL: str

    # Keycloak Authentication
    KEYCLOAK_SERVER_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_BROWSER_URL: str | None = None

    # Outbox Publisher
    OUTBOX_PUBLISHER_BATCH_SIZE: int = Field(default=50, gt=0)
    OUTBOX_PUBLISHER_POLL_INTERVAL_SECONDS: float = Field(default=1.0, gt=0.0)
    OUTBOX_PUBLISHER_LEASE_SECONDS: int = Field(default=30, gt=0)

    # Phase 10: Job Execution & Recovery
    JOB_EXECUTION_LEASE_SECONDS: int = Field(default=300, gt=0)
    JOB_RECOVERY_BATCH_SIZE: int = Field(default=50, gt=0)
    JOB_RECOVERY_POLL_INTERVAL_SECONDS: float = Field(default=5.0, gt=0.0)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def keycloak_issuer(self) -> str:
        """Construct the expected issuer URL for JWT validation."""
        server = self.KEYCLOAK_SERVER_URL.rstrip('/')
        return f"{server}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_issuers(self) -> list[str]:
        """List of acceptable issuers for JWT validation."""
        issuers = [self.keycloak_issuer]
        if self.KEYCLOAK_BROWSER_URL:
            browser_server = self.KEYCLOAK_BROWSER_URL.rstrip('/')
            browser_issuer = f"{browser_server}/realms/{self.KEYCLOAK_REALM}"
            if browser_issuer not in issuers:
                issuers.append(browser_issuer)
        return issuers

    @property
    def keycloak_jwks_url(self) -> str:
        """Construct the JWKS discovery URL."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    @model_validator(mode="after")
    def validate_production_hardening(self) -> 'Settings':
        if not self.is_production:
            return self

        # 1. Validate SECRET_KEY in production
        if not self.SECRET_KEY or not self.SECRET_KEY.strip():
            raise ValueError("In production, SECRET_KEY must be provided and non-empty")
        secret_clean = self.SECRET_KEY.strip()
        if len(secret_clean) < 32:
            raise ValueError("In production, SECRET_KEY must have at least 32 characters")
        secret_lower = secret_clean.lower()
        if any(marker in secret_lower for marker in INSECURE_SECRET_MARKERS):
            raise ValueError("In production, SECRET_KEY must not contain insecure placeholder phrases")
        if len(set(secret_clean)) == 1:
            raise ValueError("In production, SECRET_KEY must not consist of repeated single characters")
        if len(set(secret_clean)) < 8:
            raise ValueError("In production, SECRET_KEY has insufficient character variety (at least 8 distinct characters required)")
        if re.fullmatch(r"(.{1,16})\1+", secret_clean):
            raise ValueError("In production, SECRET_KEY must not consist of a simple repeated pattern")

        # 2. Validate KEYCLOAK_CLIENT_SECRET in production
        if not self.KEYCLOAK_CLIENT_SECRET or not self.KEYCLOAK_CLIENT_SECRET.strip():
            raise ValueError("In production, KEYCLOAK_CLIENT_SECRET must be set")
        if any(marker in self.KEYCLOAK_CLIENT_SECRET.lower() for marker in INSECURE_SECRET_MARKERS):
            raise ValueError("In production, KEYCLOAK_CLIENT_SECRET must not use insecure placeholder values")

        # 3. Validate RABBITMQ_URL in production (must not use default guest:guest, plain or URL-encoded)
        try:
            parsed_rmq = urlsplit(self.RABBITMQ_URL)
            if "@" in parsed_rmq.netloc:
                userinfo = parsed_rmq.netloc.rsplit("@", 1)[0]
                userinfo_decoded = unquote(userinfo)
                if ":" in userinfo_decoded:
                    rmq_user, rmq_pass = userinfo_decoded.split(":", 1)
                    if rmq_user.strip().lower() == "guest" and rmq_pass.strip().lower() == "guest":
                        raise ValueError("In production, default guest:guest credentials must not be used for RABBITMQ_URL")
        except ValueError:
            raise
        except Exception:
            pass

        return self

    model_config = {"env_file": [".env", "../.env"], "case_sensitive": True, "extra": "ignore"}


settings = Settings()
