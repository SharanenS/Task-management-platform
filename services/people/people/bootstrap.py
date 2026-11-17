"""Operator-only initial administrator provisioning. No public bootstrap endpoint."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib import parse, request
from uuid import UUID, uuid4, uuid5

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from taskspace_security.settings import SecuritySettings

from .models import Account, CompanyRoleGrant, EmployeeProfile, InitialAdminProvisioning

LOCK_KEY = 7461736


class ProvisioningError(RuntimeError):
    """Only fixed reason codes may cross the operator boundary."""


class IdentityProvider:
    def __init__(self, settings, operator_password):
        url = parse.urlsplit(settings.jwks_url)
        self.origin = url.scheme + "://" + url.netloc
        self.grant = None
        self.password = operator_password

    def __enter__(self):
        data = parse.urlencode(
            {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "portal-bootstrap",
                "password": self.password,
            }
        ).encode()
        with request.urlopen(
            request.Request(
                self.origin + "/realms/master/protocol/openid-connect/token", data=data
            ),
            timeout=5,
        ) as response:
            self.grant = json.load(response)
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.grant and self.grant.get("refresh_token"):
            try:
                data = parse.urlencode(
                    {"client_id": "admin-cli", "refresh_token": self.grant["refresh_token"]}
                ).encode()
                with request.urlopen(
                    request.Request(
                        self.origin + "/realms/master/protocol/openid-connect/logout", data=data
                    ),
                    timeout=5,
                ) as response:
                    if response.status != 204:
                        raise ProvisioningError("operator_grant_revocation_failed")
            except Exception:
                if exc_type is not None:
                    print(
                        "Provisioning cleanup failed: operator_grant_revocation_failed",
                        file=sys.stderr,
                    )
                    return False
                raise ProvisioningError("operator_grant_revocation_failed") from None
        return False

    def call(self, path, payload=None):
        req = request.Request(
            self.origin + "/admin/realms/taskspace-portals/" + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + self.grant["access_token"],
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=5) as response:
            if payload is None:
                return json.load(response)
            location = response.headers.get("Location", "")
            return str(UUID(parse.urlsplit(location).path.rsplit("/", 1)[-1]))

    def find(self, username):
        return self.call("users?username=" + parse.quote(username, safe="") + "&exact=true")

    def get(self, subject):
        return self.call("users/" + str(UUID(subject)))

    def create(self, operation, password):
        return self.call(
            "users",
            {
                "username": operation.username,
                "enabled": True,
                "firstName": "Company",
                "lastName": "Administrator",
                "email": operation.email_marker,
                "emailVerified": True,
                "requiredActions": ["UPDATE_PASSWORD"],
                "credentials": [{"type": "password", "value": password, "temporary": True}],
            },
        )


def owned_identity(user, operation):
    start = operation.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    created = user.get("createdTimestamp", 0) / 1000
    return (
        user.get("username", "").casefold() == operation.username
        and user.get("email") == operation.email_marker
        and user.get("firstName") == "Company"
        and user.get("lastName") == "Administrator"
        and start.timestamp() - 1 <= created <= start.timestamp() + 300
    )


def ensure_initial_administrator(session, provider, issuer, username, password, *, now=None):
    username = username.casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,99}", username) or len(password) < 32:
        raise ProvisioningError("invalid_initial_administrator_configuration")
    admins = session.scalars(
        select(Account)
        .join(CompanyRoleGrant)
        .where(Account.issuer == issuer, CompanyRoleGrant.role == "ADMIN")
        .order_by(Account.created_at, Account.id)
    ).all()
    if admins:
        first_username = None
        for account in admins:
            if not account.active or not account.profile or not account.profile.active:
                raise ProvisioningError("existing_administrator_requires_review")
            user = provider.get(account.subject)
            if user.get("id") != account.subject or not user.get("enabled"):
                raise ProvisioningError("existing_administrator_identity_requires_review")
            if first_username is None:
                first_username = user["username"]
        return {
            "created": False,
            "status": "existing_administrator",
            "subject": admins[0].subject,
            "accountId": admins[0].id,
            "username": first_username,
        }
    operation = session.get(InitialAdminProvisioning, "initial-admin")
    if operation and operation.state == "COMPLETE":
        raise ProvisioningError("completed_administrator_requires_manual_recovery")
    if operation is None:
        operation_id = str(uuid4())
        operation = InitialAdminProvisioning(
            key="initial-admin",
            operation_id=operation_id,
            username=username,
            email_marker="bootstrap-" + operation_id + "@example.invalid",
            state="PENDING_IDENTITY",
            started_at=now or datetime.now(timezone.utc),
        )
        session.add(operation)
        session.commit()
    if operation.username != username:
        raise ProvisioningError("initial_administrator_request_changed")
    newly_created = False
    if not operation.subject:
        matches = provider.find(username)
        if len(matches) > 1:
            raise ProvisioningError("ambiguous_existing_identity")
        if matches:
            user = matches[0]
            if not owned_identity(user, operation):
                raise ProvisioningError("existing_identity_not_owned")
            subject = str(UUID(user["id"]))
        else:
            subject = provider.create(operation, password)
            newly_created = True
        user = provider.get(subject)
        if not owned_identity(user, operation) or not user.get("enabled"):
            raise ProvisioningError("created_identity_ownership_mismatch")
        if newly_created and "UPDATE_PASSWORD" not in user.get("requiredActions", []):
            raise ProvisioningError("temporary_password_change_not_required")
        operation.subject = subject
        operation.state = "IDENTITY_CREATED"
        session.commit()
    user = provider.get(operation.subject)
    if user.get("id") != operation.subject or not user.get("enabled"):
        raise ProvisioningError("provisioned_identity_requires_review")
    if session.scalar(
        select(Account).where(Account.issuer == issuer, Account.subject == operation.subject)
    ):
        raise ProvisioningError("existing_account_must_not_be_promoted")
    account_id = str(uuid5(UUID(operation.operation_id), "account"))
    account = Account(id=account_id, issuer=issuer, subject=operation.subject, active=True)
    account.profile = EmployeeProfile(
        id=str(uuid5(UUID(operation.operation_id), "profile")),
        display_name="Company Administrator",
        active=True,
    )
    account.grants = [CompanyRoleGrant(role="ADMIN")]
    session.add(account)
    operation.state = "COMPLETE"
    session.commit()
    return {
        "created": newly_created,
        "status": "created" if newly_created else "resumed",
        "subject": account.subject,
        "accountId": account.id,
        "operationId": operation.operation_id,
        "username": operation.username,
    }


def main():
    value = json.load(sys.stdin)
    settings = SecuritySettings.from_environment()
    engine = create_engine(os.environ["PEOPLE_DATABASE_URL"], hide_parameters=True)
    if engine.url.database != "taskspace_people" or engine.url.host != "people-db":
        raise ProvisioningError("wrong_people_database_boundary")
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        connection.commit()
        try:
            with (
                Session(bind=connection) as session,
                IdentityProvider(settings, value["operatorPassword"]) as provider,
            ):
                result = ensure_initial_administrator(
                    session,
                    provider,
                    settings.issuer,
                    value["username"],
                    value["temporaryPassword"],
                )
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            connection.commit()
    engine.dispose()
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except ProvisioningError as error:
        print("Initial administrator provisioning failed: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print(
            "Initial administrator provisioning failed; private details omitted.", file=sys.stderr
        )
        sys.exit(1)
