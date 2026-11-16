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
    args = parser.parse_args()
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
    if len(owned) != 4 or any(
        not x["State"]["Running"] or x["State"].get("Health", {}).get("Status") != "healthy"
        for x in owned
    ):
        raise RuntimeError("Four healthy isolated authentication services are required")
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
            if len(own_after) == 4 and all(
                x["State"]["Running"] and x["State"].get("Health", {}).get("Status") == "healthy"
                for x in own_after
            ):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Authentication service restoration failed")
            time.sleep(1)
        if {x["Id"]: health(x) for x in after if x["Id"] in legacy} != legacy:
            raise RuntimeError("Legacy service state changed during acceptance")
        print("Four new services healthy; legacy service IDs and health unchanged.", flush=True)
    if not args.recovery:
        created_receipts = set(receipt_dir.glob("*.json")) - prior_receipts
        if not created_receipts or (code == 0 and len(created_receipts) != 1):
            raise RuntimeError("Acceptance identity creation scope was incomplete")
        for path in created_receipts:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("status") != "cleaned" or not all(
                receipt.get(key)
                for key in ("identityRemoved", "bootstrapPreserved", "grantsRevoked")
            ):
                raise RuntimeError(
                    "Scoped identity or administrator-grant cleanup was not verified"
                )
        print(
            "Scoped disposable identity cleanup and bootstrap/grant preservation verified.",
            flush=True,
        )
    report = json.loads((ROOT / "apps/web/test-results/s1-acceptance.json").read_text())
    expected = 2 if args.recovery else 5
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
    (
        destination / f"{args.project}-{'recovery' if args.recovery else 'lifecycle'}.json"
    ).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
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
