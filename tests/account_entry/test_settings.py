import pytest
from taskspace_security.settings import SecuritySettings


def configure(monkeypatch):
    monkeypatch.setenv("AUTH_ISSUER", "http://127.0.0.1:8180/realms/taskspace-portals")
    monkeypatch.setenv(
        "AUTH_JWKS_URL",
        "http://identity:8080/realms/taskspace-portals/protocol/openid-connect/certs",
    )
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_HTTP", "true")
    monkeypatch.setenv("PEOPLE_SERVICE_KEY", "s" * 43)


def test_explicit_scoped_local_provider_is_supported(monkeypatch):
    configure(monkeypatch)
    assert SecuritySettings.from_environment().audience == "taskspace-portals-api"


@pytest.mark.parametrize(
    "name,value",
    [
        ("AUTH_ISSUER", "http://untrusted:8180/realms/taskspace-portals"),
        ("AUTH_ISSUER", "http://127.0.0.1:8181/realms/taskspace-portals"),
        (
            "AUTH_JWKS_URL",
            "http://untrusted:8080/realms/taskspace-portals/protocol/openid-connect/certs",
        ),
        (
            "AUTH_JWKS_URL",
            "http://identity:8081/realms/taskspace-portals/protocol/openid-connect/certs",
        ),
        (
            "AUTH_JWKS_URL",
            "http://identity:8080/realms/taskspace-portals/protocol/openid-connect/certs?secret=value",
        ),
        ("PEOPLE_SERVICE_KEY", "short"),
        ("AUTH_ALLOW_LOCAL_HTTP", "false"),
    ],
)
def test_untrusted_boundary_fails_closed(monkeypatch, name, value):
    configure(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        SecuritySettings.from_environment()
