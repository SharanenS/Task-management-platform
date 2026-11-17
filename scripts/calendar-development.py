"""Operate the isolated S6 calendar domain only after runtime/migration approval."""

import argparse
import importlib.util
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "account_operations", ROOT / "scripts/account-management-development.py"
)
accounts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accounts)
PRIVATE = ROOT / ".local/calendar/development.json"


def environment():
    if not PRIVATE.exists():
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        with PRIVATE.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    k: secrets.token_urlsafe(48)
                    for k in ("PROJECT_WORK_SERVICE_KEY", "PROJECT_WORK_DATABASE_PASSWORD")
                },
                stream,
            )
        if os.name != "nt":
            PRIVATE.chmod(0o600)
    return {**accounts.environment(), **json.loads(PRIVATE.read_text(encoding="utf-8"))}


def compose(*args, capture=False):
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ROOT / ".local/auth/compose.defaults"),
            "--project-name",
            "taskspace-portals-development",
            *sum(
                (
                    ["-f", name]
                    for name in (
                        "compose.yaml",
                        "compose.auth.yaml",
                        "compose.account-entry.yaml",
                        "compose.accounts.yaml",
                        "compose.calendar.yaml",
                    )
                ),
                [],
            ),
            *args,
        ],
        cwd=ROOT,
        env=environment(),
        capture_output=capture,
        text=True,
        check=False,
    )


def preflight():
    accounts.account.SERVICES.update({"mailbox", "project-work", "project-work-db"})
    accounts.preflight()
    if compose("config", "--quiet", capture=True).returncode:
        raise RuntimeError("calendar_configuration_invalid")
    print("Private calendar service/database configuration verified; no new public business ports.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "up", "status", "stop"))
    parser.add_argument("--apply-migration", action="store_true")
    args = parser.parse_args()
    if args.action == "status":
        return compose("ps").returncode
    if args.action == "stop":
        return compose(
            "stop",
            "web",
            "gateway",
            "project-work",
            "project-work-db",
            "people",
            "people-db",
            "identity",
            "identity-db",
            "auth-sessions",
            "mailbox",
        ).returncode
    preflight()
    if args.action == "preflight":
        return 0
    if not args.apply_migration:
        raise RuntimeError("migration_approval_required")
    owned = subprocess.check_output(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=com.docker.compose.project=taskspace-portals-development",
            "--filter",
            "label=com.docker.compose.service=people",
        ],
        text=True,
    ).split()
    if not owned:
        if subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/account-management-development.py"),
                "up",
                "--apply-migration",
            ],
            cwd=ROOT,
        ).returncode:
            return 1
    elif len(owned) != 1:
        raise RuntimeError("people_service_ambiguous")
    for service in ("project-work", "gateway", "web"):
        if compose("build", service).returncode:
            return 1
    for arguments in [
        ("up", "-d", "--no-deps", "--wait", "--wait-timeout", "180", "project-work-db"),
        ("up", "-d", "--no-deps", "project-work"),
        ("exec", "-T", "project-work", "alembic", "upgrade", "head"),
        (
            "up",
            "-d",
            "--no-deps",
            "--wait",
            "--wait-timeout",
            "180",
            "project-work",
            "gateway",
            "web",
        ),
    ]:
        if compose(*arguments).returncode:
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("Calendar operation failed; private configuration details omitted.", file=sys.stderr)
        sys.exit(1)
