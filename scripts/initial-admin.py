"""Provision the application administrator explicitly; never reset existing credentials."""

import argparse
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / ".local/admin/initial-admin.json"
spec = importlib.util.spec_from_file_location(
    "auth_operations", ROOT / "scripts/auth-development.py"
)
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


class InitialAdministratorError(RuntimeError):
    """Contains a fixed diagnostic reason code, never provider response data."""


def configuration(username):
    if not PRIVATE.exists():
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        with PRIVATE.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "username": username,
                    "temporaryPassword": secrets.token_urlsafe(32) + "aA1!",
                    "purpose": "initial administrator; valid until first password change",
                },
                stream,
                indent=2,
            )
        if os.name != "nt":
            PRIVATE.chmod(0o600)
    value = json.loads(PRIVATE.read_text(encoding="utf-8"))
    if value["username"].casefold() != username.casefold():
        raise InitialAdministratorError("administrator_configuration_conflict")
    return value


def people_container():
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.project=taskspace-portals-development",
            "--filter",
            "label=com.docker.compose.service=people",
            "--format",
            "{{.ID}}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    identity = result.stdout.strip()
    if not re.fullmatch("[a-f0-9]{12}", identity):
        raise InitialAdministratorError("people_service_ambiguous")
    inspect = json.loads(
        subprocess.check_output(
            ["docker", "inspect", identity, "--format", "{{json .}}"], text=True
        )
    )
    if (
        inspect["Config"]["Labels"].get("com.docker.compose.project")
        != "taskspace-portals-development"
        or inspect["Config"]["Labels"].get("com.docker.compose.service") != "people"
        or inspect["State"]["Health"]["Status"] != "healthy"
    ):
        raise InitialAdministratorError("people_service_scope_or_health_mismatch")
    return identity


def ensure(container, config):
    value = {
        "username": config["username"],
        "temporaryPassword": config["temporaryPassword"],
        "operatorPassword": auth.credentials()["AUTH_BOOTSTRAP_PASSWORD"],
    }
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-m", "people.bootstrap"],
        input=json.dumps(value),
        text=True,
        capture_output=True,
    )
    if result.returncode:
        codes = re.findall(r"Initial administrator provisioning failed: ([a-z_]+)", result.stderr)
        raise InitialAdministratorError(
            codes[0] if codes else "initial_administrator_provisioning_failed"
        )
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="ADMIN")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expect-created", action="store_true")
    args = parser.parse_args()
    config = configuration(args.username)
    container = people_container()
    first = ensure(container, config)
    if args.expect_created and not first["created"]:
        raise InitialAdministratorError("fresh_administrator_provisioning_not_exercised")
    if args.verify:
        second = ensure(container, config)
        if (
            second["created"]
            or first["subject"] != second["subject"]
            or first["accountId"] != second["accountId"]
        ):
            raise InitialAdministratorError("administrator_idempotency_failed")
    if first["created"]:
        config["issuedForSubject"] = first["subject"]
        PRIVATE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (PRIVATE.parent / "last-result.json").write_text(
        json.dumps(first, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Initial application administrator "
        + (
            "created with required first-login password change."
            if first["created"]
            else "preserved; no password or role was changed."
        )
    )
    if args.verify:
        print("Repeated provisioning preserved the exact administrator identity and account.")


if __name__ == "__main__":
    try:
        main()
    except InitialAdministratorError as error:
        print(
            "Initial administrator operation failed: " + str(error) + ". Private details omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception:
        print(
            "Initial administrator operation failed; private details omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
