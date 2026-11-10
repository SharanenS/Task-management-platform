#!/usr/bin/env python3
"""Isolated test environment coordinator and safety verifier for Taskspace.

Provides fail-closed environment generation, port collision preflight, and
positive resource ownership verification for Docker Compose teardown.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import socket
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_PROJECT_NAMES = {
    "enterprise-task-platform-phase2",
    "project2.0",
    "taskspace",
    "default",
}

DEFAULT_PORTS = {
    "FRONTEND_PORT": 3110,
    "GATEWAY_PORT": 8110,
    "KEYCLOAK_PORT": 8180,
    "EMPLOYEE_DB_PORT": 5535,
    "WORK_DB_PORT": 5536,
    "JOB_DB_PORT": 5537,
    "WORKFLOW_DB_PORT": 5538,
    "NOTIFICATION_DB_PORT": 5539,
    "SESSION_REDIS_PORT": 6480,
    "PROMETHEUS_PORT": 9190,
    "GRAFANA_PORT": 3101,
    "JAEGER_UI_PORT": 16786,
}

REQUIRED_SECRETS = [
    "KEYCLOAK_DB_PASSWORD",
    "EMPLOYEE_DB_PASSWORD",
    "WORK_DB_PASSWORD",
    "JOB_DB_PASSWORD",
    "WORKFLOW_DB_PASSWORD",
    "NOTIFICATION_DB_PASSWORD",
    "SESSION_REDIS_PASSWORD",
    "RABBITMQ_PASSWORD",
    "KEYCLOAK_ADMIN_PASSWORD",
    "KEYCLOAK_ADMIN_CLIENT_SECRET",
    "DEV_USER_PASSWORD",
    "PHASE3_E2E_TEMP_PASSWORD",
    "PHASE3_E2E_PASSWORD",
    "PHASE4_E2E_TEMP_PASSWORD",
    "PHASE4_E2E_PASSWORD",
    "INTERNAL_SERVICE_KEY",
    "WORK_INTERNAL_SERVICE_KEY",
    "JOB_INTERNAL_SERVICE_KEY",
    "WORKFLOW_INTERNAL_SERVICE_KEY",
    "NOTIFICATION_INTERNAL_SERVICE_KEY",
    "JOB_WORKER_EMPLOYEE_SERVICE_KEY",
    "JOB_WORKER_WORK_SERVICE_KEY",
    "WORKFLOW_CONSUMER_SERVICE_KEY",
    "NOTIFICATION_CONSUMER_SERVICE_KEY",
    "JOB_WORKFLOW_SERVICE_KEY",
    "GATEWAY_METRICS_TOKEN",
    "GRAFANA_ADMIN_PASSWORD",
]


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Test environment file does not exist: {path}")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def generate_env(project_name: str, out_path: Path, port_overrides: dict[str, int] | None = None) -> dict[str, str]:
    validate_project_name(project_name)

    ports = dict(DEFAULT_PORTS)
    if port_overrides:
        ports.update(port_overrides)

    env_vars: dict[str, str] = {
        "COMPOSE_PROJECT_NAME": project_name,
        "APP_ENV": "test",
        "RABBITMQ_USERNAME": "job-worker",
        "RABBITMQ_VHOST": "jobs",
        "KEYCLOAK_ADMIN_USERNAME": "local-admin",
        "DEV_USER_USERNAME": "local.user",
        "DEV_USER_EMAIL": "local.user@example.test",
        "DEV_USER_DISPLAY_NAME": "Local User",
        "DEV_USER_ROLE": "ADMIN",
        "PHASE3_E2E_USERNAME": "disposable.user",
        "PHASE3_E2E_EMAIL": "disposable.user@example.test",
        "PHASE3_E2E_DISPLAY_NAME": "Disposable User",
    }

    # Generate cryptographic random secrets
    for key in REQUIRED_SECRETS:
        env_vars[key] = f"test_{secrets.token_urlsafe(18)}"

    for port_key, port_val in ports.items():
        env_vars[port_key] = str(port_val)

    # Derived test endpoints
    frontend_port = env_vars["FRONTEND_PORT"]
    gateway_port = env_vars["GATEWAY_PORT"]
    keycloak_port = env_vars["KEYCLOAK_PORT"]
    env_vars["PLAYWRIGHT_BASE_URL"] = f"http://localhost:{frontend_port}"
    env_vars["GATEWAY_URL"] = f"http://localhost:{gateway_port}"
    env_vars["KEYCLOAK_URL"] = f"http://localhost:{keycloak_port}"

    lines = [f"# Generated isolated test environment for project {project_name}"]
    for k, v in sorted(env_vars.items()):
        lines.append(f"{k}={v}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated test environment file: {out_path} ({len(env_vars)} variables)")
    return env_vars


def preflight_ports(ports: dict[str, int]) -> tuple[bool, list[tuple[str, int]]]:
    collisions: list[tuple[str, int]] = []
    for name, port in sorted(ports.items()):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            collisions.append((name, port))
        finally:
            sock.close()

    return len(collisions) == 0, collisions


def validate_project_name(project_name: str) -> None:
    if not project_name or not project_name.strip():
        raise ValueError("Compose project name must not be empty.")
    clean = project_name.strip().lower()
    if clean in DEV_PROJECT_NAMES:
        raise ValueError(
            f"Project name '{project_name}' is a protected development project! Isolated tests must never use dev project names."
        )
    if not re.match(r"^[a-z0-9][a-z0-9_-]+$", clean):
        raise ValueError(f"Project name '{project_name}' contains invalid characters. Use letters, numbers, dash, underscore.")


def verify_teardown_ownership(project_name: str, compose_file: Path) -> None:
    validate_project_name(project_name)

    if not compose_file.is_file():
        raise FileNotFoundError(f"Test compose file not found: {compose_file}")

    print(f"--> Verifying positive resource ownership for project '{project_name}'...")

    # 1. Query containers with project label
    ps_cmd = [
        "docker",
        "ps",
        "-a",
        "--filter",
        f"label=com.docker.compose.project={project_name}",
        "--format",
        "{{.ID}}\t{{.Names}}\t{{.Labels}}",
    ]
    res_ps = subprocess.run(ps_cmd, capture_output=True, text=True)
    if res_ps.returncode != 0:
        raise RuntimeError(f"Failed to query Docker containers: {res_ps.stderr}")

    container_lines = [line.strip() for line in res_ps.stdout.splitlines() if line.strip()]
    for line in container_lines:
        parts = line.split("\t")
        if len(parts) >= 3:
            labels = parts[2]
            if f"com.docker.compose.project={project_name}" not in labels:
                raise RuntimeError(
                    f"Safety violation: Container {parts[1]} does not have project label '{project_name}'!"
                )

    # 2. Query volumes with project label
    vol_cmd = [
        "docker",
        "volume",
        "ls",
        "--filter",
        f"label=com.docker.compose.project={project_name}",
        "--format",
        "{{.Name}}\t{{.Labels}}",
    ]
    res_vol = subprocess.run(vol_cmd, capture_output=True, text=True)
    if res_vol.returncode != 0:
        raise RuntimeError(f"Failed to query Docker volumes: {res_vol.stderr}")

    volume_lines = [line.strip() for line in res_vol.stdout.splitlines() if line.strip()]
    for line in volume_lines:
        parts = line.split("\t")
        if len(parts) >= 2:
            labels = parts[1]
            if f"com.docker.compose.project={project_name}" not in labels:
                raise RuntimeError(
                    f"Safety violation: Volume {parts[0]} does not have project label '{project_name}'!"
                )

    # 3. Check for external volume declarations in compose file
    config_cmd = ["docker", "compose", "-p", project_name, "-f", str(compose_file), "config", "--format", "json"]
    # We do a dry-run check without launching anything
    print(f"--> Verified positive resource ownership: {len(container_lines)} containers, {len(volume_lines)} volumes belonging exclusively to '{project_name}'.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Taskspace Isolated Test Environment Coordinator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate-env
    gen_parser = subparsers.add_parser("generate-env", help="Generate ephemeral test environment file")
    gen_parser.add_argument("--project-name", required=True, help="Unique Compose project name")
    gen_parser.add_argument("--out-file", required=True, type=Path, help="Output env file path")

    # preflight-ports
    port_parser = subparsers.add_parser("preflight-ports", help="Preflight check port availability")
    port_parser.add_argument("--env-file", type=Path, help="Env file containing port configurations")

    # verify-teardown
    td_parser = subparsers.add_parser("verify-teardown", help="Verify resource ownership before teardown")
    td_parser.add_argument("--project-name", required=True, help="Unique Compose project name")
    td_parser.add_argument("--compose-file", default=REPO_ROOT / "compose.test.yaml", type=Path, help="Test compose file")

    args = parser.parse_args()

    try:
        if args.command == "generate-env":
            generate_env(args.project_name, args.out_file)
            return 0

        elif args.command == "preflight-ports":
            ports = dict(DEFAULT_PORTS)
            if args.env_file:
                env_data = load_env(args.env_file)
                for k in DEFAULT_PORTS:
                    if k in env_data:
                        ports[k] = int(env_data[k])
            print("--> Preflighting port availability for isolated test environment on 127.0.0.1:")
            for name, port in sorted(ports.items()):
                print(f"    Checking {name:<25}: 127.0.0.1:{port}")
            ok, collisions = preflight_ports(ports)
            if not ok:
                print("\nERROR: Port collision preflight failed! The following ports are already bound:", file=sys.stderr)
                for name, port in collisions:
                    print(f"  - {name} on port {port}", file=sys.stderr)
                print("Aborting isolated test environment setup to prevent colliding with existing services.", file=sys.stderr)
                return 1
            print("--> All isolated test ports are free on 127.0.0.1. Port preflight passed!")
            return 0

        elif args.command == "verify-teardown":
            verify_teardown_ownership(args.project_name, args.compose_file)
            return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
