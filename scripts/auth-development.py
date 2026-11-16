"""Operate only the isolated Taskspace authentication development stack."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / ".local/auth/development.json"
PROJECT = "taskspace-portals-development"
SERVICES = {"web", "identity", "identity-db", "auth-sessions"}


def credentials() -> dict[str, str]:
    if not PRIVATE.exists():
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            name: secrets.token_urlsafe(32)
            for name in ("AUTH_DATABASE_PASSWORD", "AUTH_BOOTSTRAP_PASSWORD", "AUTH_REDIS_PASSWORD")
        }
        with PRIVATE.open("x", encoding="utf-8") as stream:
            json.dump(data, stream)
        if os.name != "nt":
            PRIVATE.chmod(0o600)
    return json.loads(PRIVATE.read_text(encoding="utf-8"))


def compose_env() -> dict[str, str]:
    return {**os.environ, **credentials(), "TASKSPACE_WEB_PORT": "3020"}


def compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    defaults = PRIVATE.parent / "compose.defaults"
    defaults.parent.mkdir(parents=True, exist_ok=True)
    if not defaults.exists():
        defaults.write_text("# No legacy environment is inherited.\n", encoding="utf-8")
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
            *args,
        ],
        cwd=ROOT,
        env=compose_env(),
        text=True,
        capture_output=capture,
        check=False,
    )


def preflight() -> None:
    result = compose("config", "--quiet", capture=True)
    if result.returncode:
        raise RuntimeError("Authentication Compose configuration is invalid")
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{json .}}"], text=True, capture_output=True, check=True
    )
    owned_ports: set[int] = set()
    for line in result.stdout.splitlines():
        item = json.loads(line)
        labels = dict(
            part.split("=", 1) for part in item.get("Labels", "").split(",") if "=" in part
        )
        if labels.get("com.docker.compose.project") == PROJECT:
            if labels.get("com.docker.compose.service") not in SERVICES:
                raise RuntimeError("Unexpected service in replacement project")
            for port in (3020, 8180, 6381):
                if f"127.0.0.1:{port}->" in item.get("Ports", ""):
                    owned_ports.add(port)
    for port in (3020, 8180, 6381):
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                if port not in owned_ports:
                    raise RuntimeError(f"Port {port} belongs to another process") from None
    print("Authentication configuration and isolated ports verified.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "up", "status", "stop"))
    args = parser.parse_args()
    if args.action == "preflight":
        preflight()
        return 0
    if args.action == "up":
        preflight()
        for service in ("identity", "web"):
            result = compose("build", service)
            if result.returncode:
                return result.returncode
        return compose("up", "-d", "--wait", "--wait-timeout", "180").returncode
    if args.action == "status":
        return compose("ps").returncode
    return compose("stop", "web", "identity", "auth-sessions", "identity-db").returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(
            "Authentication operation failed; inspect service status. Private values are omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
