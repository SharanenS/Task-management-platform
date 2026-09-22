import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_development_config_valid_defaults():
    s = Settings(
        ENVIRONMENT="development",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672//",
        KEYCLOAK_SERVER_URL="http://localhost:8080",
        KEYCLOAK_REALM="test",
        KEYCLOAK_CLIENT_ID="test-client",
    )
    assert s.ENVIRONMENT == "development"
    assert not s.is_production
    assert s.OUTBOX_PUBLISHER_BATCH_SIZE == 50
    assert s.JOB_EXECUTION_LEASE_SECONDS == 300


def test_invalid_numeric_settings():
    with pytest.raises(ValidationError) as exc:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://guest:guest@localhost:5672//",
            KEYCLOAK_SERVER_URL="http://localhost:8080",
            KEYCLOAK_REALM="test",
            KEYCLOAK_CLIENT_ID="test-client",
            OUTBOX_PUBLISHER_BATCH_SIZE=0,
        )
    assert "OUTBOX_PUBLISHER_BATCH_SIZE" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://guest:guest@localhost:5672//",
            KEYCLOAK_SERVER_URL="http://localhost:8080",
            KEYCLOAK_REALM="test",
            KEYCLOAK_CLIENT_ID="test-client",
            JOB_EXECUTION_LEASE_SECONDS=-5,
        )
    assert "JOB_EXECUTION_LEASE_SECONDS" in str(exc.value)


# ---------------------------------------------------------------------------
# Production SECRET_KEY validation tests
# ---------------------------------------------------------------------------

def test_production_fails_on_empty_secret_key():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="",
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_fails_on_whitespace_only_secret_key():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="   \t\n   ",
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_fails_on_short_secret_key():
    # 31 characters - just below 32-character boundary
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="1234567890abcdef1234567890abcde",  # len 31
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_fails_on_repeated_single_character_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="a" * 36,
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_fails_on_low_variety_secret():
    # Length 36 but only 4 distinct characters ('a', 'b', 'c', 'd')
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="abcdabcdabcdabcdabcdabcdabcdabcdabcd",
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_fails_on_simple_repeated_pattern():
    # 8 distinct chars ("12345678"), but is a trivial repeated 8-char pattern (len 32)
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="12345678123456781234567812345678",
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_fails_on_placeholder_markers():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://produser:prodpass@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
            SECRET_KEY="your_development_secret_key_change_in_production_9999",
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_succeeds_with_strong_secret_and_boundary():
    # Exactly 32 characters, high variety (> 8 distinct chars), no pattern
    boundary_secret = "k7P#9mQ2$vL5xR8@wN1*yB4&zT6!sC3%"
    assert len(boundary_secret) == 32
    s = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://prod_user:prod_pw@postgres:5432/taskplatform",
        RABBITMQ_URL="amqp://prod_broker_user:prod_broker_pw@rabbitmq:5672//",
        KEYCLOAK_SERVER_URL="https://auth.enterprise.internal",
        KEYCLOAK_REALM="enterprise",
        KEYCLOAK_CLIENT_ID="task-platform",
        SECRET_KEY=boundary_secret,
        KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
    )
    assert s.is_production


# ---------------------------------------------------------------------------
# Production RABBITMQ_URL credential validation tests
# ---------------------------------------------------------------------------

def test_production_fails_on_plain_guest_guest_rabbitmq():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://guest:guest@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            SECRET_KEY="a_very_secure_random_production_secret_key_that_is_32_plus_chars",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
        )
    assert "RABBITMQ_URL" in str(exc.value)


def test_production_fails_on_url_encoded_colon_guest_guest():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://guest%3Aguest@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            SECRET_KEY="a_very_secure_random_production_secret_key_that_is_32_plus_chars",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
        )
    assert "RABBITMQ_URL" in str(exc.value)


def test_production_fails_on_percent_encoded_username_password():
    # %67%75%65%73%74 == guest
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://%67%75%65%73%74:%67%75%65%73%74@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            SECRET_KEY="a_very_secure_random_production_secret_key_that_is_32_plus_chars",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
        )
    assert "RABBITMQ_URL" in str(exc.value)


def test_production_fails_on_mixed_percent_encoded_guest():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            RABBITMQ_URL="amqp://guest%3a%67uest@rabbitmq:5672//",
            KEYCLOAK_SERVER_URL="https://auth.example.com",
            KEYCLOAK_REALM="enterprise",
            KEYCLOAK_CLIENT_ID="task-platform",
            SECRET_KEY="a_very_secure_random_production_secret_key_that_is_32_plus_chars",
            KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
        )
    assert "RABBITMQ_URL" in str(exc.value)


def test_production_accepts_valid_dedicated_and_encoded_passwords():
    # Dedicated production credentials with standard characters
    s1 = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        RABBITMQ_URL="amqp://prod_app_user:prod_secret_pass_123@rabbitmq:5672//",
        KEYCLOAK_SERVER_URL="https://auth.example.com",
        KEYCLOAK_REALM="enterprise",
        KEYCLOAK_CLIENT_ID="task-platform",
        SECRET_KEY="a_very_secure_random_production_secret_key_that_is_32_plus_chars",
        KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
    )
    assert s1.is_production

    # Dedicated credentials with percent-encoded special characters (%40 is @, %21 is !)
    s2 = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        RABBITMQ_URL="amqp://prod_user:p%40ss%21word@rabbitmq:5672//",
        KEYCLOAK_SERVER_URL="https://auth.example.com",
        KEYCLOAK_REALM="enterprise",
        KEYCLOAK_CLIENT_ID="task-platform",
        SECRET_KEY="a_very_secure_random_production_secret_key_that_is_32_plus_chars",
        KEYCLOAK_CLIENT_SECRET="secure_production_client_secret_xyz123",
    )
    assert s2.is_production


def test_keycloak_issuers_default_without_browser_url():
    s = Settings(
        ENVIRONMENT="development",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672//",
        KEYCLOAK_SERVER_URL="http://keycloak:8080",
        KEYCLOAK_REALM="enterprise",
        KEYCLOAK_CLIENT_ID="task-platform",
    )
    assert s.KEYCLOAK_BROWSER_URL is None
    assert s.keycloak_issuer == "http://keycloak:8080/realms/enterprise"
    assert s.keycloak_issuers == ["http://keycloak:8080/realms/enterprise"]


def test_keycloak_issuers_with_browser_url():
    s = Settings(
        ENVIRONMENT="development",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672//",
        KEYCLOAK_SERVER_URL="http://keycloak:8080",
        KEYCLOAK_REALM="enterprise",
        KEYCLOAK_CLIENT_ID="task-platform",
        KEYCLOAK_BROWSER_URL="http://localhost:8180",
    )
    assert s.KEYCLOAK_BROWSER_URL == "http://localhost:8180"
    assert s.keycloak_issuer == "http://keycloak:8080/realms/enterprise"
    assert s.keycloak_issuers == [
        "http://keycloak:8080/realms/enterprise",
        "http://localhost:8180/realms/enterprise",
    ]

