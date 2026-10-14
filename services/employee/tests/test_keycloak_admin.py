import httpx
import pytest

from app.keycloak_admin import KeycloakAdmin, KeycloakCollisionError, KeycloakUnavailableError


def make_response(
    status: int, data: object | None = None, headers: dict[str, str] | None = None
) -> httpx.Response:
    return httpx.Response(
        status, json=data, headers=headers, request=httpx.Request("GET", "http://idp")
    )


def test_token_uses_client_credentials_and_bounded_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> httpx.Response:
        observed.update(url=url, **kwargs)
        return make_response(200, {"access_token": "opaque-token"})

    monkeypatch.setattr(httpx, "post", post)
    assert KeycloakAdmin()._token() == "opaque-token"
    assert observed["timeout"] == 5.0
    assert observed["data"] == {
        "grant_type": "client_credentials",
        "client_id": "taskspace-employee-admin",
        "client_secret": "development-only-placeholder",
    }


@pytest.mark.parametrize(
    "failure", [make_response(401, {"error": "denied"}), make_response(200, {})]
)
def test_token_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, failure: httpx.Response
) -> None:
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: failure)
    with pytest.raises(KeycloakUnavailableError) as caught:
        KeycloakAdmin()._token()
    assert str(caught.value) == ""


def test_connection_failure_is_sanitized_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def post(*args: object, **kwargs: object) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("sensitive upstream detail")

    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(KeycloakUnavailableError) as caught:
        KeycloakAdmin()._token()
    assert attempts == 1
    assert str(caught.value) == ""


def test_owned_user_lookup_and_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = KeycloakAdmin()
    monkeypatch.setattr(
        admin,
        "_request",
        lambda *args, **kwargs: make_response(
            200, [{"id": "subject", "attributes": {"taskspaceProvisioningKey": ["request"]}}]
        ),
    )
    assert admin.find_owned_user("employee", "request").subject == "subject"
    with pytest.raises(KeycloakCollisionError):
        admin.find_owned_user("employee", "other")


def test_disabled_user_has_temporary_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = KeycloakAdmin()
    observed: dict[str, object] = {}

    def request(method: str, path: str, **kwargs: object) -> httpx.Response:
        observed.update(method=method, path=path, **kwargs)
        return make_response(201, headers={"Location": "http://idp/users/subject"})

    monkeypatch.setattr(admin, "_request", request)
    subject = admin.create_disabled_user(
        username="employee",
        email="employee@example.test",
        display_name="Employee User",
        temporary_password="temporary-value",
        ownership_key="request-key",
    )
    assert subject == "subject"
    payload = observed["json"]
    assert isinstance(payload, dict)
    assert payload["enabled"] is False
    assert payload["credentials"] == [
        {"type": "password", "value": "temporary-value", "temporary": True}
    ]


@pytest.mark.parametrize("enabled", [True, False])
def test_enable_and_disable(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    admin = KeycloakAdmin()
    observed: dict[str, object] = {}

    def request(method: str, path: str, **kwargs: object) -> httpx.Response:
        observed.update(method=method, path=path, **kwargs)
        return make_response(204)

    monkeypatch.setattr(admin, "_request", request)
    admin.set_enabled("subject", enabled)
    assert observed == {"method": "PUT", "path": "/users/subject", "json": {"enabled": enabled}}


def test_malformed_upstream_responses_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = KeycloakAdmin()
    monkeypatch.setattr(
        admin, "_request", lambda *args, **kwargs: make_response(200, {"bad": True})
    )
    with pytest.raises(KeycloakUnavailableError):
        admin.find_owned_user("employee", "request")
    monkeypatch.setattr(admin, "_request", lambda *args, **kwargs: make_response(201))
    with pytest.raises(KeycloakUnavailableError):
        admin.create_disabled_user(
            username="employee",
            email="employee@example.test",
            display_name="Employee User",
            temporary_password="temporary-value",
            ownership_key="request-key",
        )
