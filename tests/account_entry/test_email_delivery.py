import ssl
from contextlib import contextmanager
from copy import deepcopy

import email_delivery as delivery
import pytest


class SMTP:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self, context):
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        self.calls.append("starttls")

    def login(self, user, password):
        assert user == "dailygotasks@gmail.com" and password == "abcdefghijklmnop"
        self.calls.append("login")


@pytest.fixture
def boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "ROOT", tmp_path)
    smtp = SMTP()
    monkeypatch.setattr(delivery.smtplib, "SMTP", lambda host, port, timeout: smtp)
    state = {"settings": deepcopy(delivery.CAPTURE), "puts": 0}

    @contextmanager
    def realm():
        def call(method, payload=None):
            assert method in {"GET", "PUT"}
            if method == "PUT":
                assert set(payload) == {"smtpServer"}
                state["settings"] = deepcopy(payload["smtpServer"])
                state["puts"] += 1
            return {"smtpServer": state["settings"]} if method == "GET" else None

        yield call, deepcopy(state["settings"])

    monkeypatch.setattr(delivery, "realm_access", realm)
    return smtp, state, tmp_path


def test_gmail_configuration_requires_verified_tls_before_login_and_updates_email_only(boundary):
    smtp, state, path = boundary
    delivery.configure_gmail("abcd efgh ijkl mnop")
    assert smtp.calls == ["ehlo", "starttls", "ehlo", "login"]
    assert state["puts"] == 1 and state["settings"]["host"] == "smtp.gmail.com"
    receipt = (path / ".local/accounts/email-delivery.json").read_text(encoding="utf-8")
    assert "abcdefghijklmnop" not in receipt and '"recipientDeliveryVerified": false' in receipt


@pytest.mark.parametrize(
    "values",
    [
        {"host": "other.example"},
        {"port": "25"},
        {"starttls": "false"},
        {"auth": "false"},
        {"from": "other@gmail.com"},
        {"user": "other@gmail.com"},
        {"ssl": "true"},
    ],
)
def test_gmail_recognition_requires_the_exact_sender_and_encryption(values):
    settings = delivery.gmail_settings("abcdefghijklmnop")
    settings.update(values)
    assert not delivery.is_gmail(settings)


def test_automated_email_acceptance_fails_closed_when_gmail_is_active(boundary):
    smtp, state, path = boundary
    state["settings"] = delivery.gmail_settings("abcdefghijklmnop")
    with pytest.raises(delivery.EmailConfigurationError, match="capture_email_required"):
        delivery.assert_capture_delivery()
    assert state["puts"] == 0


def test_capture_acceptance_is_read_only(boundary):
    smtp, state, path = boundary
    delivery.assert_capture_delivery()
    assert state["puts"] == 0 and not smtp.calls


def test_failed_gmail_authentication_keeps_the_working_delivery(boundary, monkeypatch):
    smtp, state, path = boundary

    def fail(*args, **kwargs):
        raise RuntimeError("private credential details")

    monkeypatch.setattr(smtp, "login", fail)
    with pytest.raises(
        delivery.EmailConfigurationError, match="gmail_authentication_failed"
    ) as error:
        delivery.configure_gmail("abcdefghijklmnop")
    assert "private" not in str(error.value) and state["settings"] == delivery.CAPTURE
    assert state["puts"] == 0 and not (path / ".local/accounts/email-delivery.json").exists()


def test_unrelated_smtp_configuration_is_not_overwritten(boundary):
    smtp, state, path = boundary
    state["settings"] = {"host": "existing.example"}
    with pytest.raises(delivery.EmailConfigurationError, match="requires_review"):
        delivery.configure_gmail("abcdefghijklmnop")
    assert state["puts"] == 0


@pytest.mark.parametrize("value", ["", "short", "a" * 17, "a" * 15 + "\n"])
def test_invalid_app_password_has_no_connection_or_configuration_effect(boundary, value):
    smtp, state, path = boundary
    with pytest.raises(delivery.EmailConfigurationError):
        delivery.configure_gmail(value)
    assert not smtp.calls and state["puts"] == 0
