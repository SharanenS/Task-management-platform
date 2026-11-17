"""Realm-scoped identity administration; passwords and action links never cross this API."""

import json
import os
from urllib import parse, request
from uuid import UUID


class IdentityAdministrationError(Exception):
    pass


class IdentityAdministration:
    def __init__(self, settings):
        url = parse.urlsplit(settings.jwks_url)
        self.origin = url.scheme + "://" + url.netloc
        self.realm = "/realms/taskspace-portals"
        self.token = None

    def __enter__(self):
        secret = os.environ.get("IDENTITY_ADMIN_CLIENT_SECRET", "")
        if len(secret) < 32:
            raise IdentityAdministrationError()
        data = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": "taskspace-account-administration",
                "client_secret": secret,
            }
        ).encode()
        try:
            with request.urlopen(
                request.Request(
                    self.origin + self.realm + "/protocol/openid-connect/token",
                    data=data,
                ),
                timeout=5,
            ) as response:
                self.token = json.load(response)["access_token"]
        except Exception:
            raise IdentityAdministrationError() from None
        return self

    def __exit__(self, *args):
        self.token = None

    def call(self, method, path, payload=None):
        try:
            req = request.Request(
                self.origin + "/admin" + self.realm + "/" + path,
                method=method,
                data=None if payload is None else json.dumps(payload).encode(),
                headers={
                    "Authorization": "Bearer " + self.token,
                    "Content-Type": "application/json",
                },
            )
            with request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return json.load(response)
                if response.status == 201:
                    return str(
                        UUID(parse.urlsplit(response.headers["Location"]).path.rsplit("/", 1)[-1])
                    )
                return None
        except Exception:
            raise IdentityAdministrationError() from None

    def find(self, username, email):
        users = {}
        for key, value in (("username", username), ("email", email)):
            for user in self.call("GET", "users?" + parse.urlencode({key: value, "exact": "true"})):
                users[user["id"]] = user
        return list(users.values())

    def get(self, subject):
        return self.call("GET", "users/" + str(UUID(subject)))

    def create(self, operation):
        names = operation.display_name.split(maxsplit=1)
        return self.call(
            "POST",
            "users",
            {
                "username": operation.username,
                "firstName": names[0],
                "lastName": names[1] if len(names) == 2 else "",
                "email": operation.email,
                "emailVerified": False,
                "enabled": True,
                "requiredActions": ["VERIFY_EMAIL", "UPDATE_PASSWORD"],
                "attributes": {"taskspaceProvisioningId": [operation.id]},
            },
        )

    def enabled(self, subject, active):
        self.call("PUT", "users/" + str(UUID(subject)), {"enabled": active})

    def logout(self, subject):
        self.call("POST", "users/" + str(UUID(subject)) + "/logout")

    def email_actions(self, subject):
        origin = os.environ.get("ACCOUNT_WEB_ORIGIN", "")
        if origin != "http://127.0.0.1:3020" and not (
            origin.startswith("https://")
            and parse.urlsplit(origin).path == ""
            and not parse.urlsplit(origin).query
            and not parse.urlsplit(origin).username
        ):
            raise IdentityAdministrationError()
        query = parse.urlencode(
            {
                "client_id": "taskspace-portals-web",
                "redirect_uri": origin + "/sign-in",
                "lifespan": "900",
            }
        )
        self.call(
            "PUT",
            "users/" + str(UUID(subject)) + "/execute-actions-email?" + query,
            ["VERIFY_EMAIL", "UPDATE_PASSWORD"],
        )
