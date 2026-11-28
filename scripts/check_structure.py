"""Check S0 source, dependency and execution boundaries without starting services."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY_JOBS = (
    "static-and-unit",
    "schema-and-codegen",
    "dependency-audit",
    "postgres-integration",
    "e2e-acceptance",
    "reliability-and-recovery",
)
REQUIRED_FILES = (
    "scripts/scheduling-development.py",
    "scripts/run-s12-source-checks.py",
    "scripts/verify-scheduling-postgres.py",
    "services/project-work/project_work/scheduling.py",
    "services/project-work/project_work/schedule_graph.py",
    "services/project-work/migrations/versions/0007_task_scheduling.py",
    "apps/web/tests/e2e/task-scheduling.spec.ts",
    "scripts/task-breakdown-development.py",
    "scripts/run-s11-source-checks.py",
    "scripts/verify-tasks-postgres.py",
    "services/project-work/project_work/tasks.py",
    "services/project-work/migrations/versions/0006_task_breakdown.py",
    "apps/web/tests/e2e/task-breakdown.spec.ts",
    "scripts/owner-decisions-development.py",
    "scripts/run-s10-source-checks.py",
    "scripts/verify-owner-postgres.py",
    "services/project-work/project_work/owner_decisions.py",
    "services/project-work/migrations/versions/0005_owner_decisions.py",
    "apps/web/tests/e2e/owner-decisions.spec.ts",
    "services/project-work/project_work/memberships.py",
    "services/project-work/migrations/versions/0003_project_membership.py",
    "services/people/people/project_directory.py",
    "apps/web/tests/e2e/project-membership.spec.ts",
    "scripts/run-s8-source-checks.py",
    "scripts/membership-development.py",
    "scripts/coordination-development.py",
    "scripts/run-s9-source-checks.py",
    "scripts/verify-coordination-postgres.py",
    "services/project-work/project_work/coordination.py",
    "services/project-work/migrations/versions/0004_manager_coordination.py",
    "apps/web/tests/e2e/project-coordination.spec.ts",
    "services/project-work/project_work/projects.py",
    "services/project-work/migrations/versions/0002_manager_projects.py",
    "services/gateway/gateway/project_schema.py",
    "apps/web/src/app/manager/layout.tsx",
    "apps/web/src/app/admin/projects/page.tsx",
    "apps/web/tests/e2e/manager-projects.spec.ts",
    "scripts/run-s7-source-checks.py",
    "services/project-work/project_work/calendar.py",
    "services/project-work/project_work/app.py",
    "services/project-work/requirements.lock",
    "compose.calendar.yaml",
    "scripts/calendar-development.py",
    "scripts/run-s6-source-checks.py",
    "apps/web/src/app/admin/calendar/page.tsx",
    "services/people/migrations/versions/0004_company_structure.py",
    "services/people/people/organization.py",
    "services/gateway/gateway/organization_schema.py",
    "apps/web/src/app/admin/employees/page.tsx",
    "apps/web/src/app/admin/organization/page.tsx",
    "tests/account_entry/postgres_organization_check.py",
    "scripts/email_delivery.py",
    "scripts/configure-email.py",
    "compose.accounts.yaml",
    "scripts/account-management-development.py",
    "services/people/migrations/versions/0003_account_management.py",
    "apps/web/src/app/admin/accounts/page.tsx",
    "scripts/initial-admin.py",
    "apps/web/src/app/admin/layout.tsx",
    "services/people/migrations/versions/0002_initial_admin.py",
    "compose.auth.yaml",
    "scripts/run-s1-acceptance.py",
    "apps/web/src/shared/auth/policy.ts",
    "scripts/run_structure_tests.py",
    "tests/structure/test_repository_structure.py",
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "apps/web/next.config.ts",
    "apps/web/Dockerfile",
    "apps/web/src/app/layout.tsx",
    "apps/web/src/app/page.tsx",
    "compose.yaml",
    "legacy/compose.yaml",
    "legacy/compose.test.yaml",
    "legacy/frontend/package.json",
    "legacy/frontend/package-lock.json",
    "legacy/gateway/requirements.lock",
    "legacy/services/employee/requirements.lock",
    "legacy/services/work/requirements.lock",
    "legacy/services/job/requirements.lock",
    "legacy/services/workflow/requirements.lock",
    "legacy/services/notification/requirements.lock",
    "legacy/scripts/verify_test_reports.py",
    "legacy/scripts/isolated_test_env.py",
    "infrastructure/keycloak/taskspace-realm.json",
    ".github/workflows/ci.yml",
)


def check_repository(root: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            errors.append(f"Required source file is missing: {name}")
    if errors:
        return errors

    if "python scripts/account-management-development.py up --apply-migration" not in (
        root / ".github/workflows/ci.yml"
    ).read_text(encoding="utf-8"):
        errors.append("S4 account management runtime acceptance is missing")

    for name in ("frontend", "gateway", "services/employee", "services/work"):
        if (root / name).exists():
            errors.append(f"Previous source root is outside legacy: {name}")

    ci_source = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    if "python scripts/account-management-development.py up --apply-migration" not in ci_source:
        errors.append("S4 account management runtime acceptance is missing")

    for entry in (
        "python scripts/calendar-development.py up --apply-migration",
        "python scripts/run-s6-source-checks.py",
    ):
        if entry not in ci_source:
            errors.append("S6 calendar runtime or source acceptance is missing")

    if "python scripts/run-s7-source-checks.py" not in ci_source:
        errors.append("S7 project source acceptance is missing")

    for entry in (
        "python scripts/run-s8-source-checks.py",
        "python scripts/membership-development.py up --apply-migration",
        "python scripts/verify-membership-postgres.py",
    ):
        if entry not in ci_source:
            errors.append("S8 membership source/runtime acceptance is missing")

    runner_source = (root / "scripts/run-s1-acceptance.py").read_text(encoding="utf-8")
    for required in (
        "python scripts/run-s9-source-checks.py",
        "python scripts/coordination-development.py up --apply-migration",
        "python scripts/verify-coordination-postgres.py",
    ):
        if required not in ci_source:
            errors.append("S9 coordination source/runtime acceptance is missing")
    for required in (
        "python scripts/run-s10-source-checks.py",
        "python scripts/owner-decisions-development.py up --apply-migration",
        "python scripts/verify-owner-postgres.py",
    ):
        if required not in ci_source:
            errors.append("S10 owner-decision source/runtime acceptance is missing")
    for required in (
        "python scripts/run-s11-source-checks.py",
        "python scripts/task-breakdown-development.py up --apply-migration",
        "python scripts/verify-tasks-postgres.py",
    ):
        if required not in ci_source:
            errors.append("S11 task source/runtime acceptance is missing")
    for required in (
        "python scripts/run-s12-source-checks.py",
        "python scripts/scheduling-development.py up --apply-migration",
        "python scripts/verify-scheduling-postgres.py",
    ):
        if required not in ci_source:
            errors.append("S12 scheduling source/runtime acceptance is missing")
    if 'specs.append("tests/e2e/task-scheduling.spec.ts")' not in runner_source:
        errors.append("S12 scheduling browser acceptance is missing from full lifecycle")
    if 'specs.append("tests/e2e/task-breakdown.spec.ts")' not in runner_source:
        errors.append("S11 task browser acceptance is missing from full lifecycle")
    if 'specs.append("tests/e2e/owner-decisions.spec.ts")' not in runner_source:
        errors.append("S10 owner-decision browser acceptance is missing from full lifecycle")
    if 'specs.append("tests/e2e/project-coordination.spec.ts")' not in runner_source:
        errors.append("S9 coordination browser acceptance is missing from full lifecycle")
    if 'specs.append("tests/e2e/project-membership.spec.ts")' not in runner_source:
        errors.append("S8 membership browser acceptance is missing from full lifecycle")
    if 'specs.append("tests/e2e/manager-projects.spec.ts")' not in runner_source:
        errors.append("S7 project browser acceptance is missing from full lifecycle")
    guard = runner_source.find("assert_capture_delivery()")
    launch = runner_source.find("result = subprocess.run")
    if guard < 0 or launch < 0 or guard > launch:
        errors.append("Gmail-safe browser acceptance guard is missing")

    app = root / "apps/web"
    package = json.loads((app / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((app / "package-lock.json").read_text(encoding="utf-8"))
    for group in ("dependencies", "devDependencies"):
        dependencies = package.get(group, {})
        if lock["packages"][""].get(group, {}) != dependencies:
            errors.append(f"Application lockfile differs from {group}")
        for name, version in dependencies.items():
            if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.]+)?", version):
                errors.append(f"Application dependency is not exactly pinned: {name}")

    for path in (app / "src").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".css"}:
            continue
        source = path.read_text(encoding="utf-8")
        imports = re.findall(
            r"(?:from\s*|import\s*\(?|require\s*\()"
            r"[\s]*[\"']([^\"']+)[\"']",
            source,
        )
        for target in imports:
            if "legacy" in target.lower():
                errors.append(f"Application imports legacy code: {path.relative_to(root)}")
            if target.startswith("."):
                resolved = (path.parent / target).resolve()
                if not resolved.is_relative_to(app.resolve()):
                    errors.append(f"Application import escapes its boundary: {target}")

    config = (app / "next.config.ts").read_text(encoding="utf-8")
    if "outputFileTracingRoot: applicationRoot" not in config:
        errors.append("Application output tracing must stay inside apps/web")

    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    if "name: taskspace-portals-development" not in compose:
        errors.append("Replacement Compose project is not independently named")
    service_names = re.findall(r"^  ([a-z][a-z0-9-]*):$", compose, re.MULTILINE)
    if service_names != ["web"]:
        errors.append("S0 Compose must contain only the new web scaffold")
    if "context: ./apps/web" not in compose:
        errors.append("Replacement Docker build context must be apps/web")
    if "legacy" in compose or "volumes:" in compose:
        errors.append("S0 replacement must not attach legacy services or persistent data")
    if "TASKSPACE_WEB_PORT:-3020" not in compose:
        errors.append("Replacement web port must be distinct from the legacy default")

    legacy = (root / "legacy/compose.yaml").read_text(encoding="utf-8")
    if not legacy.startswith("name: enterprise-task-platform-phase2"):
        errors.append("Existing legacy Compose project identity changed")
    if "./infrastructure/" in legacy.replace("../infrastructure/", ""):
        errors.append("Legacy bind mounts must resolve to shared infrastructure")

    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for name in LEGACY_JOBS:
        match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z][a-z0-9-]*:|\Z)", ci, re.M | re.S)
        if not match or "working-directory: legacy" not in match.group(1):
            errors.append(f"Legacy CI gate or relocated execution root is missing: {name}")
        if f"needs.{name}.result" not in ci:
            errors.append(f"Mandatory CI result is not checked: {name}")
    if "needs.s1-authentication.result" not in ci or "  s1-authentication:" not in ci:
        errors.append("S1 authentication CI gate is missing")
    for required in (
        "suite: [desktop, tablet, mobile, recovery]",
        "fail-fast: false",
        "needs: [s1-authentication-suites]",
        "${{ needs.s1-authentication-suites.result }}",
        'if [ "$SUITES_RESULT" != "success" ]; then',
    ):
        if required not in ci:
            errors.append("S1 independent suites or fail-closed aggregation is missing")
    for suite in ("desktop", "tablet", "mobile", "recovery"):
        command = (
            "python scripts/run-s1-acceptance.py --project desktop --recovery"
            if suite == "recovery"
            else f"python scripts/run-s1-acceptance.py --project {suite}"
        )
        if f"if: matrix.suite == '{suite}'\n        run: {command}\n" not in ci:
            errors.append(f"S1 independent {suite} acceptance is missing")
    if "needs.s2-account-entry.result" not in ci or "  s2-account-entry:" not in ci:
        errors.append("S2 account-entry CI gate is missing")
    if "python scripts/initial-admin.py --verify --expect-created" not in ci:
        errors.append("S3 initial administrator CI acceptance is missing")
    if "needs.s0-structure.result" not in ci:
        errors.append("S0 CI gate is missing from mandatory result validation")
    for match in re.finditer(r"cache-dependency-path:\s*([^\n]+)", ci):
        name = match.group(1).strip().strip("'").strip('"')
        if "*" not in name and not (root / name).is_file():
            errors.append(f"CI dependency cache path is missing: {name}")
    return errors


def main() -> int:
    errors = check_repository(ROOT)
    for message in errors:
        print(message, file=sys.stderr)
    if errors:
        return 1
    print("S0 source and execution boundaries verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
