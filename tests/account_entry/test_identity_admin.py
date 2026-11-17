import io
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from people.identity_admin import IdentityAdministration, IdentityAdministrationError


class Response(io.BytesIO):
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_action_email_uses_fixed_client_redirect_short_lifetime_and_no_password(monkeypatch):
    monkeypatch.setenv("ACCOUNT_WEB_ORIGIN", "http://127.0.0.1:3020")
    provider = IdentityAdministration(
        SimpleNamespace(
            jwks_url="http://identity:8080/realms/taskspace-portals/protocol/openid-connect/certs"
        )
    )
    provider.token = "fixture-token"
    subject = str(uuid4())
    calls = []

    def send(req, timeout):
        calls.append(req)
        url = urlsplit(req.full_url)
        assert url.scheme == "http" and url.netloc == "identity:8080"
        assert (
            url.path
            == "/admin/realms/taskspace-portals/users/" + subject + "/execute-actions-email"
        )
        assert parse_qs(url.query) == {
            "client_id": ["taskspace-portals-web"],
            "redirect_uri": ["http://127.0.0.1:3020/sign-in"],
            "lifespan": ["900"],
        }
        assert req.get_method() == "PUT" and json.loads(req.data) == [
            "VERIFY_EMAIL",
            "UPDATE_PASSWORD",
        ]
        return Response()

    monkeypatch.setattr("people.identity_admin.request.urlopen", send)
    provider.email_actions(subject)
    assert len(calls) == 1


def test_identity_failure_does_not_expose_upstream_details(monkeypatch):
    provider = IdentityAdministration(
        SimpleNamespace(
            jwks_url="https://identity.example/realms/taskspace-portals/protocol/openid-connect/certs"
        )
    )
    provider.token = "fixture-token"

    def fail(*args, **kwargs):
        raise RuntimeError("private upstream details")

    monkeypatch.setattr("people.identity_admin.request.urlopen", fail)
    with pytest.raises(IdentityAdministrationError) as error:
        provider.get(str(uuid4()))
    assert "private" not in str(error.value)


def test_runtime_identity_client_requires_a_private_secret(monkeypatch):
    monkeypatch.delenv("IDENTITY_ADMIN_CLIENT_SECRET", raising=False)
    provider = IdentityAdministration(SimpleNamespace(jwks_url="https://identity.example/certs"))
    with pytest.raises(IdentityAdministrationError):
        provider.__enter__()


def test_creation_maps_the_supplied_name_and_never_installs_a_password(monkeypatch):
    provider = IdentityAdministration(SimpleNamespace(jwks_url="https://identity.example/certs"))
    operation = SimpleNamespace(
        username="new.user",
        email="new@example.test",
        display_name="Given Family Name",
        id=str(uuid4()),
    )
    captured = []
    monkeypatch.setattr(
        provider, "call", lambda method, path, payload: captured.append(payload) or str(uuid4())
    )
    provider.create(operation)
    assert captured[0]["firstName"] == "Given" and captured[0]["lastName"] == "Family Name"
    assert "credentials" not in captured[0] and captured[0]["requiredActions"] == [
        "VERIFY_EMAIL",
        "UPDATE_PASSWORD",
    ]
