"""Verify isolated S1 browser acceptance, restoration and zero-skip execution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "taskspace-portals-development"


def inventory() -> list[dict]:
    ids = subprocess.run(
        ["docker", "ps", "-aq"], capture_output=True, text=True, check=True
    ).stdout.split()
    if not ids:
        return []
    return json.loads(
        subprocess.run(
            ["docker", "inspect", *ids], capture_output=True, text=True, check=True
        ).stdout
    )


def health(item: dict) -> tuple:
    return (item["Id"], item["State"]["Running"], item["State"].get("Health", {}).get("Status"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", choices=("desktop", "tablet", "mobile"), default="desktop")
    parser.add_argument("--recovery", action="store_true")
    parser.add_argument("--account-entry-only", action="store_true")
    parser.add_argument("--admin-only", action="store_true")
    parser.add_argument("--accounts-only", action="store_true")
    parser.add_argument("--organization-only", action="store_true")
    parser.add_argument("--calendar-only", action="store_true")
    args = parser.parse_args()
    focuses = [
        args.account_entry_only,
        args.admin_only,
        args.accounts_only,
        args.organization_only,
        args.calendar_only,
    ]
    if sum(focuses) > 1 or (args.recovery and any(focuses)):
        raise RuntimeError("Acceptance focus cannot run outages or another focus")
    receipt_dir = ROOT / ".local/auth/runs"
    prior_receipts = set(receipt_dir.glob("*.json"))
    before = inventory()
    legacy = {
        x["Id"]: health(x)
        for x in before
        if x["Config"]["Labels"].get("com.docker.compose.project")
        == "enterprise-task-platform-phase2"
    }
    owned = [
        x for x in before if x["Config"]["Labels"].get("com.docker.compose.project") == PROJECT
    ]
    expected_services = {
        "web",
        "identity",
        "identity-db",
        "auth-sessions",
        "gateway",
        "people",
        "people-db",
        "mailbox",
    }
    calendar_services = {"project-work", "project-work-db"}
    actual_names = {x["Config"]["Labels"].get("com.docker.compose.service") for x in owned}
    if actual_names & calendar_services:
        expected_services |= calendar_services
    if args.calendar_only and not calendar_services <= actual_names:
        raise RuntimeError("Calendar services are required")
    expected_count = len(expected_services)
    service_names = [x["Config"]["Labels"].get("com.docker.compose.service") for x in owned]
    if (
        len(owned) != expected_count
        or set(service_names) != expected_services
        or any(
            not x["State"]["Running"] or x["State"].get("Health", {}).get("Status") != "healthy"
            for x in owned
        )
    ):
        raise RuntimeError(f"{expected_count} healthy isolated portal services are required")
    from email_delivery import assert_capture_delivery

    if not (
        args.admin_only or args.account_entry_only or args.organization_only or args.calendar_only
    ):
        assert_capture_delivery()
    env = os.environ.copy()
    if args.recovery:
        if args.project != "desktop":
            raise RuntimeError("Recovery runs are desktop-only")
        env["S1_RECOVERY"] = "1"
    spec = "tests/e2e/recovery.spec.ts" if args.recovery else "tests/e2e/authentication.spec.ts"
    try:
        result = subprocess.run(
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                spec,
                "--project=" + args.project,
                "--workers=1",
                "--retries=0",
                *(["--grep", "S2 current account status"] if args.account_entry_only else []),
                *(["--grep", "S3 administrator workspace"] if args.admin_only else []),
                *(["--grep", "S4 account creation"] if args.accounts_only else []),
                *(["--grep", "S5 company structure"] if args.organization_only else []),
                *(["--grep", "S6 versioned working calendar"] if args.calendar_only else []),
            ],
            cwd=ROOT / "apps/web",
            env=env,
            check=False,
        )
        code = result.returncode
    finally:
        for item in owned:
            service = item["Config"]["Labels"].get("com.docker.compose.service")
            current = next((x for x in inventory() if x["Id"] == item["Id"]), None)
            if (
                current
                and not current["State"]["Running"]
                and service in {"identity", "auth-sessions"}
                and args.recovery
            ):
                subprocess.run(["docker", "start", item["Id"]], capture_output=True, check=True)
        deadline = time.monotonic() + 45
        while True:
            after = inventory()
            own_after = [x for x in after if x["Id"] in {v["Id"] for v in owned}]
            if len(own_after) == expected_count and all(
                x["State"]["Running"] and x["State"].get("Health", {}).get("Status") == "healthy"
                for x in own_after
            ):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Authentication service restoration failed")
            time.sleep(1)
        if {x["Id"]: health(x) for x in after if x["Id"] in legacy} != legacy:
            raise RuntimeError("Legacy service state changed during acceptance")
        print(
            f"{expected_count} portal services healthy; legacy service IDs and health unchanged.",
            flush=True,
        )
    if not args.recovery:
        created_receipts = set(receipt_dir.glob("*.json")) - prior_receipts
        if not created_receipts or (code == 0 and len(created_receipts) != 1):
            raise RuntimeError("Acceptance identity creation scope was incomplete")
        for path in created_receipts:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("status") != "cleaned" or not all(
                receipt.get(key)
                for key in (
                    "identityRemoved",
                    "bootstrapPreserved",
                    "grantsRevoked",
                    "accountRemoved",
                    "organizationCleanupVerified",
                    "calendarCleanupVerified",
                )
            ):
                raise RuntimeError(
                    "Scoped identity or administrator-grant cleanup was not verified"
                )
        print(
            "Scoped disposable identity cleanup and bootstrap/grant preservation verified.",
            flush=True,
        )
    report = json.loads((ROOT / "apps/web/test-results/s1-acceptance.json").read_text())
    expected = (
        1
        if (
            args.account_entry_only
            or args.admin_only
            or args.accounts_only
            or args.organization_only
            or args.calendar_only
        )
        else (2 if args.recovery else 10)
    )
    if (
        code
        or report["status"] != "passed"
        or report["selected"] != expected
        or report["passed"] != expected
        or report["skipped"]
    ):
        raise RuntimeError("Acceptance failed or did not execute its full required scope")
    destination = ROOT / "test-results/reports/s1"
    destination.mkdir(parents=True, exist_ok=True)
    scope = (
        "calendar"
        if args.calendar_only
        else "organization"
        if args.organization_only
        else "accounts"
        if args.accounts_only
        else "admin"
        if args.admin_only
        else "account-entry"
        if args.account_entry_only
        else ("recovery" if args.recovery else "lifecycle")
    )
    (destination / f"{args.project}-{scope}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("S1 acceptance scope and zero-skip report verified.", flush=True)
    if args.recovery:
        print(
            "Verifying the complete credentialed lifecycle after service restoration.", flush=True
        )
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--project", "desktop"], check=True
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("S1 acceptance or restoration failed. Private diagnostics omitted.", file=sys.stderr)
        sys.exit(1)
