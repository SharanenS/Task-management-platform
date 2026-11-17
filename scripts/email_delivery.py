"""Explicit local operator email configuration. Never log credentials or send test mail."""

import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib import parse, request

ROOT = Path(__file__).resolve().parent.parent
SENDER = "dailygotasks@gmail.com"
ORIGIN = "http://127.0.0.1:8180"
REALM = "taskspace-portals"
CAPTURE = {
    "host": "mailbox",
    "port": "1025",
    "from": "no-reply@dailygo.local",
    "fromDisplayName": "Dailygo",
    "ssl": "false",
    "starttls": "false",
    "auth": "false",
}


class EmailConfigurationError(RuntimeError):
    """Only fixed reason codes leave this boundary."""


def gmail_settings(app_password):
    normalized = app_password.replace(" ", "")
    if not re.fullmatch(r"[a-zA-Z0-9]{16}", normalized):
        raise EmailConfigurationError("invalid_app_password_format")
    return {
        "host": "smtp.gmail.com",
        "port": "587",
        "from": SENDER,
        "fromDisplayName": "Dailygo",
        "ssl": "false",
        "starttls": "true",
        "auth": "true",
        "user": SENDER,
        "password": normalized,
    }


def is_gmail(value):
    expected = {k: v for k, v in gmail_settings("a" * 16).items() if k != "password"}
    return all(value.get(k) == v for k, v in expected.items()) and set(value).issubset(
        set(expected) | {"password"}
    )


def verify_identity_boundary():
    ids = subprocess.check_output(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=com.docker.compose.project=taskspace-portals-development",
            "--filter",
            "label=com.docker.compose.service=identity",
        ],
        text=True,
    ).split()
    if len(ids) != 1:
        raise EmailConfigurationError("identity_ownership_mismatch")
    items = json.loads(subprocess.check_output(["docker", "inspect", ids[0]], text=True))
    item = items[0]
    labels = item["Config"]["Labels"]
    ports = item.get("NetworkSettings", {}).get("Ports", {}).get("8080/tcp") or []
    if (
        labels.get("com.docker.compose.project") != "taskspace-portals-development"
        or labels.get("com.docker.compose.service") != "identity"
        or not item["State"]["Running"]
        or item["State"].get("Health", {}).get("Status") != "healthy"
        or not any(p.get("HostIp") == "127.0.0.1" and p.get("HostPort") == "8180" for p in ports)
    ):
        raise EmailConfigurationError("identity_ownership_mismatch")


@contextmanager
def realm_access():
    verify_identity_boundary()
    path = ROOT / ".local/auth/development.json"
    if not path.exists():
        raise EmailConfigurationError("local_identity_configuration_missing")
    password = json.loads(path.read_text(encoding="utf-8"))["AUTH_BOOTSTRAP_PASSWORD"]
    data = parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "portal-bootstrap",
            "password": password,
        }
    ).encode()
    grant = None
    primary_error = False
    try:
        with request.urlopen(
            request.Request(ORIGIN + "/realms/master/protocol/openid-connect/token", data=data),
            timeout=5,
        ) as response:
            grant = json.load(response)

        def call(method, payload=None):
            req = request.Request(
                ORIGIN + "/admin/realms/" + REALM,
                method=method,
                data=None if payload is None else json.dumps(payload).encode(),
                headers={
                    "Authorization": "Bearer " + grant["access_token"],
                    "Content-Type": "application/json",
                },
            )
            with request.urlopen(req, timeout=5) as response:
                return json.load(response) if response.status == 200 else None

        realm = call("GET")
        if realm.get("realm") != REALM or not realm.get("enabled"):
            raise EmailConfigurationError("realm_ownership_mismatch")
        yield call, realm.get("smtpServer") or {}
    except EmailConfigurationError:
        primary_error = True
        raise
    except Exception:
        primary_error = True
        raise EmailConfigurationError("identity_email_configuration_failed") from None
    finally:
        if grant and grant.get("refresh_token"):
            try:
                data = parse.urlencode(
                    {"client_id": "admin-cli", "refresh_token": grant["refresh_token"]}
                ).encode()
                with request.urlopen(
                    request.Request(
                        ORIGIN + "/realms/master/protocol/openid-connect/logout", data=data
                    ),
                    timeout=5,
                ) as response:
                    if response.status != 204:
                        raise EmailConfigurationError("operator_grant_revocation_failed")
            except Exception:
                if not primary_error:
                    raise EmailConfigurationError("operator_grant_revocation_failed") from None
                print(
                    "Email setup cleanup failed: operator_grant_revocation_failed", file=sys.stderr
                )


def configure_gmail(app_password):
    settings = gmail_settings(app_password)
    # Authenticate over verified STARTTLS before changing the working realm settings.
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(SENDER, settings["password"])
    except Exception:
        raise EmailConfigurationError("gmail_authentication_failed") from None
    with realm_access() as (call, current):
        if current and current != CAPTURE and not is_gmail(current):
            raise EmailConfigurationError("existing_email_configuration_requires_review")
        call("PUT", {"smtpServer": settings})
        applied = call("GET").get("smtpServer") or {}
        if not is_gmail(applied) or not applied.get("password"):
            raise EmailConfigurationError("gmail_configuration_readback_failed")
    # This receipt contains no credential and is never the authority for test safety.
    path = ROOT / ".local/accounts/email-delivery.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "mode": "gmail",
                "sender": SENDER,
                "authenticationVerified": True,
                "recipientDeliveryVerified": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)


def assert_capture_delivery():
    with realm_access() as (call, current):
        if current != CAPTURE:
            raise EmailConfigurationError("capture_email_required_for_automated_acceptance")


def delivery_status():
    with realm_access() as (call, current):
        if current == CAPTURE:
            return "local-capture"
        if is_gmail(current) and current.get("password"):
            return "gmail"
        return "unrecognized"
