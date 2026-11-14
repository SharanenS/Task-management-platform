from dataclasses import dataclass

import httpx

from app.config import settings


class KeycloakUnavailableError(Exception):
    pass


class KeycloakCollisionError(Exception):
    pass


@dataclass(frozen=True)
class KeycloakUser:
    subject: str
    ownership_key: str | None


class KeycloakAdmin:
    def _token(self) -> str:
        try:
            response = httpx.post(
                f"{settings.keycloak_admin_base_url}/realms/{settings.keycloak_realm}"
                "/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.keycloak_admin_client_id,
                    "client_secret": settings.keycloak_admin_client_secret,
                },
                timeout=5.0,
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError
            return token
        except (httpx.HTTPError, TypeError, ValueError) as error:
            raise KeycloakUnavailableError from error

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                f"{settings.keycloak_admin_base_url}/admin/realms/{settings.keycloak_realm}{path}",
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=5.0,
                params=params,
                json=json,
            )
        except httpx.HTTPError as error:
            raise KeycloakUnavailableError from error
        return response

    def find_owned_user(self, username: str, ownership_key: str) -> KeycloakUser | None:
        response = self._request("GET", "/users", params={"username": username, "exact": "true"})
        if response.status_code != 200:
            raise KeycloakUnavailableError
        try:
            users = response.json()
            if not users:
                return None
            if len(users) != 1:
                raise KeycloakCollisionError
            attributes = users[0].get("attributes") or {}
            values = attributes.get("taskspaceProvisioningKey") or []
            owned = values[0] if values else None
            if owned != ownership_key:
                raise KeycloakCollisionError
            return KeycloakUser(subject=users[0]["id"], ownership_key=owned)
        except (KeyError, TypeError, ValueError) as error:
            raise KeycloakUnavailableError from error

    def create_disabled_user(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        temporary_password: str,
        ownership_key: str,
    ) -> str:
        first, _, last = display_name.strip().partition(" ")
        response = self._request(
            "POST",
            "/users",
            json={
                "username": username,
                "email": email,
                "firstName": first,
                "lastName": last or "User",
                "enabled": False,
                "emailVerified": True,
                "attributes": {"taskspaceProvisioningKey": [ownership_key]},
                "credentials": [
                    {"type": "password", "value": temporary_password, "temporary": True}
                ],
            },
        )
        if response.status_code == 409:
            existing = self.find_owned_user(username, ownership_key)
            if existing:
                return existing.subject
            raise KeycloakCollisionError
        if response.status_code != 201:
            raise KeycloakUnavailableError
        location = response.headers.get("Location", "")
        subject = str(location.rstrip("/").rsplit("/", 1)[-1])
        if not subject:
            raise KeycloakUnavailableError
        return subject

    def set_enabled(self, subject: str, enabled: bool) -> None:
        response = self._request("PUT", f"/users/{subject}", json={"enabled": enabled})
        if response.status_code != 204:
            raise KeycloakUnavailableError


keycloak_admin = KeycloakAdmin()
