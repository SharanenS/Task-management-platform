"""Fixed deployment boundaries; never derive upstream URLs from request headers."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SecuritySettings:
    issuer: str
    jwks_url: str
    service_key: str
    audience: str = "taskspace-portals-api"
    client_id: str = "taskspace-portals-web"

    @classmethod
    def from_environment(cls):
        issuer = os.environ["AUTH_ISSUER"]
        jwks = os.environ["AUTH_JWKS_URL"]
        local = os.environ.get("AUTH_ALLOW_LOCAL_HTTP") == "true"
        for value in (issuer, jwks):
            u = urlsplit(value)
            if (
                u.username
                or u.password
                or u.query
                or u.fragment
                or not u.netloc
                or (
                    u.scheme != "https"
                    and not (
                        local and u.scheme == "http" and u.hostname in {"127.0.0.1", "identity"}
                    )
                )
            ):
                raise ValueError("Invalid provider configuration")
        if (
            urlsplit(issuer).path != "/realms/taskspace-portals"
            or urlsplit(jwks).path != "/realms/taskspace-portals/protocol/openid-connect/certs"
        ):
            raise ValueError("Invalid provider path")
        issuer_url = urlsplit(issuer)
        keys_url = urlsplit(jwks)
        if (
            issuer_url.scheme == "http"
            and issuer != "http://127.0.0.1:8180/realms/taskspace-portals"
        ):
            raise ValueError("Invalid development issuer origin")
        if keys_url.scheme == "http" and jwks not in {
            "http://identity:8080/realms/taskspace-portals/protocol/openid-connect/certs",
            "http://127.0.0.1:8180/realms/taskspace-portals/protocol/openid-connect/certs",
        }:
            raise ValueError("Invalid development key origin")
        if issuer_url.scheme == "https" and (keys_url.scheme, keys_url.netloc) != (
            issuer_url.scheme,
            issuer_url.netloc,
        ):
            raise ValueError("Invalid provider key origin")
        key = os.environ["PEOPLE_SERVICE_KEY"]
        if len(key) < 43:
            raise ValueError("Service credential is too short")
        return cls(issuer, jwks, key)
