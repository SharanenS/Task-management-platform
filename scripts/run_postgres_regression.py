#!/usr/bin/env python3
"""Run isolated PostgreSQL integration test suites for Work, Job, Workflow, and Notification services.

Creates temporary isolated databases, runs zero-to-head migrations and repeated-head checks,
executes the full pytest suite with isolation environment variables set, and guarantees clean teardown.
Supports fail-closed isolated test environment verification with machine-readable JUnit XML reports.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
    return env


@dataclass
class ServiceTarget:
    name: str
    user: str
    env_password_key: str
    default_port: int
    env_port_key: str
    test_url_env_key: str
    test_path: str
    migration_cwd: str
    expected_head: str
    expected_tests: int


TARGETS = [
    ServiceTarget(
        name="work",
        user="work",
        env_password_key="WORK_DB_PASSWORD",
        default_port=5436,
        env_port_key="WORK_DB_PORT",
        test_url_env_key="WORK_POSTGRES_TEST_URL",
        test_path="services/work/tests/test_postgres.py",
        migration_cwd="services/work",
        expected_head="20261108_03",
        expected_tests=13,
    ),
    ServiceTarget(
        name="job",
        user="job",
        env_password_key="JOB_DB_PASSWORD",
        default_port=5437,
        env_port_key="JOB_DB_PORT",
        test_url_env_key="JOB_POSTGRES_TEST_URL",
        test_path="services/job/tests/test_postgres.py",
        migration_cwd="services/job",
        expected_head="20261108_07",
        expected_tests=22,
    ),
    ServiceTarget(
        name="workflow",
        user="workflow",
        env_password_key="WORKFLOW_DB_PASSWORD",
        default_port=5438,
        env_port_key="WORKFLOW_DB_PORT",
        test_url_env_key="WORKFLOW_POSTGRES_TEST_URL",
        test_path="services/workflow/tests/test_postgres.py",
        migration_cwd="services/workflow",
        expected_head="20261108_02",
        expected_tests=3,
    ),
    ServiceTarget(
        name="notification",
        user="notification",
        env_password_key="NOTIFICATION_DB_PASSWORD",
        default_port=5439,
        env_port_key="NOTIFICATION_DB_PORT",
        test_url_env_key="NOTIFICATION_POSTGRES_TEST_URL",
        test_path="services/notification/tests/test_postgres.py",
        migration_cwd="services/notification",
        expected_head="20261029_02",
        expected_tests=5,
    ),
]


def run_target(
    target: ServiceTarget,
    env_vars: dict[str, str],
    isolated_mode: bool,
    junit_dir: Path | None,
) -> tuple[bool, str, int]:
    password = os.environ.get(target.env_password_key) or env_vars.get(target.env_password_key)
    if not password:
        return False, f"Missing {target.env_password_key} in environment or test env file", 0

    if isolated_mode:
        if target.env_port_key not in env_vars and target.env_port_key not in os.environ:
            return False, f"Isolated mode error: {target.env_port_key} is missing. Refusing to fall back to dev port.", 0
        port_str = os.environ.get(target.env_port_key) or env_vars[target.env_port_key]
    else:
        port_str = os.environ.get(target.env_port_key) or env_vars.get(target.env_port_key, str(target.default_port))

    port = int(port_str)
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")

    run_id = uuid.uuid4().hex[:8]
    temp_db_name = f"{target.name}_test_p14_{run_id}"

    admin_conn_str = f"postgresql://{target.user}:{password}@{host}:{port}/postgres"
    temp_db_url = f"postgresql+psycopg://{target.user}:{password}@{host}:{port}/{temp_db_name}"

    print(f"\n==================================================================")
    print(f"Service: {target.name.upper()} | Temporary DB: {temp_db_name} (Port: {port})")
    print(f"==================================================================")

    # 1. Create temporary database
    print(f"--> Creating isolated database {temp_db_name} on {host}:{port}...")
    try:
        with psycopg.connect(admin_conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE "{temp_db_name}";')
    except Exception as e:
        return False, f"Failed to create temporary database: {e}", 0

    test_passed = False
    tests_run = 0
    error_msg = ""

    try:
        # 2. Run zero-to-head migration
        print(f"--> Running Alembic zero-to-head migrations...")
        migration_env = os.environ.copy()
        migration_env["DATABASE_URL"] = temp_db_url
        migration_dir = REPO_ROOT / target.migration_cwd

        python_exe = sys.executable
        upgrade_cmd = [python_exe, "-m", "alembic", "upgrade", "head"]
        res = subprocess.run(upgrade_cmd, cwd=migration_dir, env=migration_env, capture_output=True, text=True)
        if res.returncode != 0:
            error_msg = f"Alembic upgrade failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            print(error_msg, file=sys.stderr)
            return False, error_msg, 0

        # Repeated head check
        res_repeat = subprocess.run(upgrade_cmd, cwd=migration_dir, env=migration_env, capture_output=True, text=True)
        if res_repeat.returncode != 0:
            error_msg = f"Alembic repeated head failed:\n{res_repeat.stderr}"
            return False, error_msg, 0

        # Verify current revision
        current_cmd = [python_exe, "-m", "alembic", "current"]
        res_cur = subprocess.run(current_cmd, cwd=migration_dir, env=migration_env, capture_output=True, text=True)
        if target.expected_head not in res_cur.stdout:
            error_msg = f"Expected migration head {target.expected_head} not found in alembic current output:\n{res_cur.stdout}"
            return False, error_msg, 0
        print(f"--> Migration head confirmed: {target.expected_head}")

        # 3. Run Pytest suite
        print(f"--> Running {target.test_path}...")
        test_env = os.environ.copy()
        test_env[target.test_url_env_key] = temp_db_url
        test_cmd = [python_exe, "-m", "pytest", str(REPO_ROOT / target.test_path), "-v", "--tb=short"]

        if junit_dir:
            junit_file = junit_dir / f"pytest-{target.name}.xml"
            test_cmd.extend(["--junitxml", str(junit_file)])

        test_res = subprocess.run(test_cmd, cwd=REPO_ROOT, env=test_env, capture_output=True, text=True)
        print(test_res.stdout)
        if test_res.stderr:
            print(test_res.stderr, file=sys.stderr)

        if test_res.returncode == 0:
            test_passed = True
            for line in test_res.stdout.splitlines():
                if "passed" in line and ("in " in line or "==" in line):
                    parts = line.strip("= ").split()
                    if len(parts) >= 2 and parts[1] == "passed":
                        tests_run = int(parts[0])

            # Machine-readable report verification
            if junit_dir:
                junit_file = junit_dir / f"pytest-{target.name}.xml"
                if not junit_file.is_file():
                    return False, f"Expected JUnit XML report not found: {junit_file}", 0
                tree = ET.parse(junit_file)
                root = tree.getroot()
                suite = root if root.tag == "testsuite" else root.find("testsuite")
                if suite is not None:
                    t_count = int(suite.attrib.get("tests", "0"))
                    f_count = int(suite.attrib.get("failures", "0"))
                    e_count = int(suite.attrib.get("errors", "0"))
                    s_count = int(suite.attrib.get("skipped", "0"))
                    if t_count < target.expected_tests:
                        return False, f"Incomplete test selection: expected {target.expected_tests}, ran {t_count}", t_count
                    if f_count > 0 or e_count > 0:
                        return False, f"JUnit report recorded {f_count} failures, {e_count} errors", t_count
                    if s_count > 0:
                        return False, f"Unexpected skipped tests: {s_count} tests skipped in mandatory suite", t_count
        else:
            error_msg = f"Pytest suite failed with returncode {test_res.returncode}"

    finally:
        # 4. Guaranteed cleanup: Terminate active connections and drop DB
        print(f"--> Dropping temporary database {temp_db_name}...")
        drop_success = False
        try:
            with psycopg.connect(admin_conn_str, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s AND pid <> pg_backend_pid();
                        """,
                        (temp_db_name,),
                    )
                    cur.execute(f'DROP DATABASE IF EXISTS "{temp_db_name}" WITH (FORCE);')
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (temp_db_name,))
                    if cur.fetchone() is None:
                        drop_success = True
                        print(f"--> Verified database {temp_db_name} cleanly dropped.")
                    else:
                        print(f"ERROR: Database {temp_db_name} was NOT dropped!", file=sys.stderr)
        except Exception as e:
            print(f"ERROR dropping temporary database {temp_db_name}: {e}", file=sys.stderr)

        if not drop_success and test_passed:
            test_passed = False
            error_msg = "Temporary database cleanup could not be verified."

    return test_passed, error_msg, tests_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Taskspace PostgreSQL Regression Gate")
    parser.add_argument("--env-file", type=Path, help="Path to test environment file")
    parser.add_argument("--isolated", action="store_true", help="Fail-closed isolated test execution mode")
    parser.add_argument("--junit-dir", type=Path, default=REPO_ROOT / "test-results" / "reports" / "postgres", help="Directory for JUnit XML reports")
    args = parser.parse_args()

    isolated_mode = args.isolated or bool(os.environ.get("ISOLATED_TEST_RUN"))
    env_vars: dict[str, str] = {}

    if isolated_mode:
        env_file = args.env_file or (Path(os.environ["TEST_ENV_FILE"]) if "TEST_ENV_FILE" in os.environ else None)
        if not env_file or not env_file.is_file():
            print("ERROR: Fail-closed isolated mode requires an existing test environment file via --env-file or TEST_ENV_FILE.", file=sys.stderr)
            print("Refusing to fall back to development .env or development database ports.", file=sys.stderr)
            return 1
        print(f"--> Running in FAIL-CLOSED isolated mode with environment file: {env_file}")
        env_vars = load_env_file(env_file)
    else:
        if args.env_file and args.env_file.is_file():
            env_vars = load_env_file(args.env_file)
        else:
            dev_env = REPO_ROOT / ".env"
            if dev_env.is_file():
                print(f"--> Running in local development mode using {dev_env}")
                env_vars = load_env_file(dev_env)
            else:
                print("WARNING: No .env file found; using process environment variables.")

    if args.junit_dir:
        args.junit_dir.mkdir(parents=True, exist_ok=True)

    total_passed = 0
    results: list[tuple[str, bool, int, str]] = []
    summary_data: dict[str, dict[str, object]] = {}

    for target in TARGETS:
        passed, err, count = run_target(target, env_vars, isolated_mode, args.junit_dir)
        results.append((target.name, passed, count, err))
        summary_data[target.name] = {
            "passed": passed,
            "tests_run": count,
            "expected_tests": target.expected_tests,
            "expected_head": target.expected_head,
            "error": err,
        }
        if passed:
            total_passed += count

    if args.junit_dir:
        summary_file = args.junit_dir / "summary.json"
        summary_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    print("\n==================================================================")
    print("PostgreSQL Isolated Regression Summary")
    print("==================================================================")
    all_ok = True
    for name, passed, count, err in results:
        status_str = f"PASS ({count} tests)" if passed else f"FAIL ({err})"
        print(f"  {name.upper():<15}: {status_str}")
        if not passed:
            all_ok = False

    print(f"\nTotal PostgreSQL integration tests passed: {total_passed} / 43")
    if all_ok:
        print("All PostgreSQL integration tests passed and temporary databases were dropped cleanly!")
        return 0
    else:
        print("One or more PostgreSQL regression targets failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
