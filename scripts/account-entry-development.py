"""Operate only the isolated portal account-entry services; never read legacy .env."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path
from urllib import parse, request

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "taskspace-portals-development"
SERVICES = {"web", "identity", "identity-db", "auth-sessions", "gateway", "people", "people-db"}
PRIVATE = ROOT / ".local/account-entry/development.json"
spec = importlib.util.spec_from_file_location(
    "auth_development", ROOT / "scripts/auth-development.py"
)
assert spec and spec.loader
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


def environment():
    if not PRIVATE.exists():
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        with PRIVATE.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    name: secrets.token_urlsafe(32)
                    for name in ("PEOPLE_DATABASE_PASSWORD", "PEOPLE_SERVICE_KEY")
                },
                stream,
            )
        if os.name != "nt":
            PRIVATE.chmod(0o600)
    return {**auth.compose_env(), **json.loads(PRIVATE.read_text(encoding="utf-8"))}


def compose(*args, capture=False):
    auth.compose_env()
    defaults = ROOT / ".local/auth/compose.defaults"
    if not defaults.exists():
        defaults.write_text("# No legacy environment.\n", encoding="utf-8")
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(defaults),
            "--project-name",
            PROJECT,
            "-f",
            "compose.yaml",
            "-f",
            "compose.auth.yaml",
            "-f",
            "compose.account-entry.yaml",
            *args,
        ],
        cwd=ROOT,
        env=environment(),
        text=True,
        capture_output=capture,
        check=False,
    )


def preflight():
    if compose("config", "--quiet", capture=True).returncode:
        raise RuntimeError("Account-entry configuration is invalid")
    listed = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, check=True
    )
    owned_ports = set()
    for line in listed.stdout.splitlines():
        item = json.loads(line)
        labels = dict(
            part.split("=", 1) for part in item.get("Labels", "").split(",") if "=" in part
        )
        if labels.get("com.docker.compose.project") != PROJECT:
            continue
        if labels.get("com.docker.compose.service") not in SERVICES:
            raise RuntimeError("Unexpected portal service")
        for port in (3020, 8180, 6381, 8020):
            if f"127.0.0.1:{port}->" in item.get("Ports", ""):
                owned_ports.add(port)
    for port in (3020, 8180, 6381, 8020):
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                if port not in owned_ports:
                    raise RuntimeError("Required port is owned by another process") from None
    print("Seven-service account-entry configuration and scoped ports verified.", flush=True)


class IdentityConfigurationError(RuntimeError):
    """Fixed diagnostic codes only; never expose provider responses or credentials."""


def configure_audience():
    origin = "http://127.0.0.1:8180"
    data = parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "portal-bootstrap",
            "password": auth.credentials()["AUTH_BOOTSTRAP_PASSWORD"],
        }
    ).encode()
    with request.urlopen(
        request.Request(origin + "/realms/master/protocol/openid-connect/token", data=data),
        timeout=5,
    ) as response:
        grant = json.load(response)
    try:

        def call(path, payload=None):
            req = request.Request(
                origin + "/admin/realms/taskspace-portals/" + path,
                data=None if payload is None else json.dumps(payload).encode(),
                headers={
                    "Authorization": "Bearer " + grant["access_token"],
                    "Content-Type": "application/json",
                },
            )
            with request.urlopen(req, timeout=5) as response:
                return json.load(response) if response.status == 200 else None

        clients = call("clients?clientId=taskspace-portals-web")
        if len(clients) != 1 or clients[0]["clientId"] != "taskspace-portals-web":
            raise IdentityConfigurationError("client_ownership_mismatch")
        client = clients[0]
        if client.get("redirectUris") != ["http://127.0.0.1:3020/auth/callback"] or not client.get(
            "publicClient"
        ):
            raise IdentityConfigurationError("client_configuration_mismatch")
        path = "clients/" + client["id"] + "/protocol-mappers/models"
        desired = json.loads(
            (ROOT / "infrastructure/auth/api-audience.json").read_text(encoding="utf-8")
        )
        existing = [value for value in call(path) if value["name"] == desired["name"]]
        if not existing:
            call(path, desired)
            existing = [value for value in call(path) if value["name"] == desired["name"]]
        if len(existing) != 1 or any(
            existing[0].get(key) != value for key, value in desired.items()
        ):
            raise IdentityConfigurationError("audience_configuration_mismatch")
        print(
            "Exact new-realm web client API audience verified; no users or roles changed.",
            flush=True,
        )
    finally:
        refresh = grant.get("refresh_token")
        if refresh:
            data = parse.urlencode({"client_id": "admin-cli", "refresh_token": refresh}).encode()
            with request.urlopen(
                request.Request(
                    origin + "/realms/master/protocol/openid-connect/logout", data=data
                ),
                timeout=5,
            ) as response:
                if response.status != 204:
                    raise IdentityConfigurationError("bootstrap_grant_revocation_failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "up", "status", "stop"))
    parser.add_argument("--apply-migration", action="store_true")
    args = parser.parse_args()
    if args.action == "preflight":
        preflight()
        return 0
    if args.action == "status":
        return compose("ps").returncode
    if args.action == "stop":
        return compose("stop", *sorted(SERVICES)).returncode
    if not args.apply_migration:
        raise RuntimeError("Starting S2 requires explicit migration authorization")
    preflight()
    identity_image = subprocess.run(
        ["docker", "image", "inspect", "taskspace-portals-identity:26.7.5"], capture_output=True
    )
    if identity_image.returncode and compose("build", "identity").returncode:
        return 1
    for service in ("people", "gateway", "web"):
        result = compose("build", service)
        if result.returncode:
            return result.returncode
    result = compose(
        "up", "-d", "--wait", "--wait-timeout", "180", "identity", "auth-sessions", "people-db"
    )
    if result.returncode:
        return result.returncode
    configure_audience()
    result = compose("up", "-d", "--no-deps", "people")
    if result.returncode:
        return result.returncode
    result = compose("exec", "-T", "people", "alembic", "upgrade", "head")
    if result.returncode:
        return result.returncode
    return compose("up", "-d", "--wait", "--wait-timeout", "180").returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IdentityConfigurationError as error:
        print(
            f"Account-entry identity setup failed: {error}. Private details omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception:
        print("Account-entry operation failed. Private diagnostics omitted.", file=sys.stderr)
        sys.exit(1)
