"""Operate S4 on the isolated portal stack; never read or alter legacy credentials."""

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

from email_delivery import is_gmail

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "account_entry", ROOT / "scripts/account-entry-development.py"
)
account = importlib.util.module_from_spec(spec)
spec.loader.exec_module(account)
PRIVATE = ROOT / ".local/accounts/development.json"


def environment():
    if not PRIVATE.exists():
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        with PRIVATE.open("x", encoding="utf-8") as stream:
            json.dump({"IDENTITY_ADMIN_CLIENT_SECRET": secrets.token_urlsafe(48)}, stream)
        if os.name != "nt":
            PRIVATE.chmod(0o600)
    return {**account.environment(), **json.loads(PRIVATE.read_text(encoding="utf-8"))}


def compose(*args, capture=False):
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ROOT / ".local/auth/compose.defaults"),
            "--project-name",
            account.PROJECT,
            "-f",
            "compose.yaml",
            "-f",
            "compose.auth.yaml",
            "-f",
            "compose.account-entry.yaml",
            "-f",
            "compose.accounts.yaml",
            *args,
        ],
        cwd=ROOT,
        env=environment(),
        capture_output=capture,
        text=True,
        check=False,
    )


def preflight():
    account.SERVICES.add("mailbox")
    account.preflight()
    if compose("config", "--quiet", capture=True).returncode:
        raise RuntimeError()
    ids = subprocess.check_output(["docker", "ps", "-aq"], text=True).split()
    items = (
        json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True)) if ids else []
    )
    owned = False
    for item in items:
        for bindings in (item.get("NetworkSettings", {}).get("Ports") or {}).values():
            if any(v.get("HostPort") == "8025" for v in bindings or []):
                labels = item["Config"]["Labels"]
                if (
                    labels.get("com.docker.compose.project") != account.PROJECT
                    or labels.get("com.docker.compose.service") != "mailbox"
                ):
                    raise RuntimeError()
                owned = True
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", 8025))
        except OSError:
            if not owned:
                raise RuntimeError() from None
    print("Isolated account management and local-only mail boundary verified.", flush=True)


def configure_identity():
    origin = "http://127.0.0.1:8180"
    data = parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "portal-bootstrap",
            "password": account.auth.credentials()["AUTH_BOOTSTRAP_PASSWORD"],
        }
    ).encode()
    with request.urlopen(
        request.Request(origin + "/realms/master/protocol/openid-connect/token", data=data),
        timeout=5,
    ) as response:
        grant = json.load(response)
    try:

        def call(method, path, payload=None):
            req = request.Request(
                origin + "/admin/realms/taskspace-portals" + path,
                method=method,
                data=None if payload is None else json.dumps(payload).encode(),
                headers={
                    "Authorization": "Bearer " + grant["access_token"],
                    "Content-Type": "application/json",
                },
            )
            with request.urlopen(req, timeout=5) as response:
                return json.load(response) if response.status == 200 else None

        clients = call("GET", "/clients?clientId=taskspace-portals-web")
        if len(clients) != 1 or not clients[0].get("publicClient"):
            raise RuntimeError()
        web = clients[0]
        old = ["http://127.0.0.1:3020/auth/callback"]
        desired = old + ["http://127.0.0.1:3020/sign-in"]
        if web.get("redirectUris") not in (old, desired):
            raise RuntimeError()
        if web["redirectUris"] != desired:
            call("PUT", "/clients/" + web["id"], {"redirectUris": desired})
        smtp = {
            "host": "mailbox",
            "port": "1025",
            "from": "no-reply@dailygo.local",
            "fromDisplayName": "Dailygo",
            "ssl": "false",
            "starttls": "false",
            "auth": "false",
        }
        realm = call("GET", "")
        existing_smtp = realm.get("smtpServer") or {}
        if not existing_smtp or existing_smtp == smtp:
            call("PUT", "", {"smtpServer": smtp})
        elif not (is_gmail(existing_smtp) and existing_smtp.get("password")):
            raise RuntimeError("existing_mail_configuration_requires_review")
        # Approved Gmail settings and their stored password are left untouched.
        profile = call("GET", "/users/profile")
        if profile.get("unmanagedAttributePolicy") != "ADMIN_EDIT":
            profile["unmanagedAttributePolicy"] = "ADMIN_EDIT"
            call("PUT", "/users/profile", profile)
        name = "taskspace-account-administration"
        clients = call("GET", "/clients?clientId=" + name)
        if not clients:
            call(
                "POST",
                "/clients",
                {
                    "clientId": name,
                    "enabled": True,
                    "publicClient": False,
                    "serviceAccountsEnabled": True,
                    "standardFlowEnabled": False,
                    "directAccessGrantsEnabled": False,
                    "fullScopeAllowed": False,
                    "secret": environment()["IDENTITY_ADMIN_CLIENT_SECRET"],
                    "attributes": {
                        "taskspaceOwner": "s4-account-management",
                        "access.token.lifespan": "60",
                    },
                },
            )
            clients = call("GET", "/clients?clientId=" + name)
        if len(clients) != 1:
            raise RuntimeError()
        client = clients[0]
        if (
            client.get("publicClient")
            or not client.get("serviceAccountsEnabled")
            or client.get("standardFlowEnabled")
            or client.get("directAccessGrantsEnabled")
            or client.get("fullScopeAllowed")
            or client.get("attributes", {}).get("taskspaceOwner") != "s4-account-management"
        ):
            raise RuntimeError("identity_client_ownership_mismatch")
        if (
            call("GET", "/clients/" + client["id"] + "/client-secret")["value"]
            != environment()["IDENTITY_ADMIN_CLIENT_SECRET"]
        ):
            raise RuntimeError("identity_client_secret_requires_review")
        service = call("GET", "/clients/" + client["id"] + "/service-account-user")
        management = call("GET", "/clients?clientId=realm-management")
        if len(management) != 1:
            raise RuntimeError()
        path = "/users/" + service["id"] + "/role-mappings/clients/" + management[0]["id"]
        roles = call("GET", "/clients/" + management[0]["id"] + "/roles")
        wanted = {"manage-users", "query-users", "view-users"}
        existing = call("GET", path)
        if any(r["name"] not in wanted for r in existing):
            raise RuntimeError("unexpected_identity_privilege")
        missing = [r for r in roles if r["name"] in wanted - {r["name"] for r in existing}]
        if missing:
            call("POST", path, missing)
        if {r["name"] for r in call("GET", path)} != wanted:
            raise RuntimeError()
        scope = "/clients/" + client["id"] + "/scope-mappings/clients/" + management[0]["id"]
        scoped = call("GET", scope)
        if any(r["name"] not in wanted for r in scoped):
            raise RuntimeError("unexpected_identity_scope")
        missing = [r for r in roles if r["name"] in wanted - {r["name"] for r in scoped}]
        if missing:
            call("POST", scope, missing)
        print(
            "Exact realm client, limited user-management roles and email delivery verified; "
            "no application users changed.",
            flush=True,
        )
    finally:
        data = parse.urlencode(
            {"client_id": "admin-cli", "refresh_token": grant["refresh_token"]}
        ).encode()
        with request.urlopen(
            request.Request(origin + "/realms/master/protocol/openid-connect/logout", data=data),
            timeout=5,
        ) as response:
            if response.status != 204:
                raise RuntimeError()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "up", "status"))
    parser.add_argument("--apply-migration", action="store_true")
    args = parser.parse_args()
    if args.action == "status":
        return compose("ps").returncode
    preflight()
    if args.action == "preflight":
        return 0
    if not args.apply_migration:
        raise RuntimeError("explicit_migration_authorization_required")
    for service in ("people", "gateway", "web"):
        if compose("build", service).returncode:
            return 1
    image = subprocess.run(
        ["docker", "image", "inspect", "taskspace-portals-identity:26.7.5"], capture_output=True
    )
    if image.returncode and compose("build", "identity").returncode:
        return 1
    # Existing dependency containers stay in place. Fresh CI also uses this path.
    if compose(
        "up",
        "-d",
        "--wait",
        "--wait-timeout",
        "180",
        "identity",
        "auth-sessions",
        "people-db",
        "mailbox",
    ).returncode:
        return 1
    configure_identity()
    if compose("up", "-d", "--no-deps", "people").returncode:
        return 1
    if compose("exec", "-T", "people", "alembic", "upgrade", "head").returncode:
        return 1
    return compose(
        "up", "-d", "--no-deps", "--wait", "--wait-timeout", "180", "people", "gateway", "web"
    ).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(
            "Account management operation failed; private configuration details omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
