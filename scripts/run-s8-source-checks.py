"""Fail-closed membership source verification with no live services or credentials."""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent


def main():
    report = ROOT / "test-results/reports/s8/source.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/projects/test_memberships.py",
            "tests/projects/test_membership_api.py",
            "tests/projects/test_membership_migration.py",
            "tests/account_entry/test_project_directory.py",
            "-q",
            "--junitxml",
            str(report),
        ],
        cwd=ROOT,
    )
    if result.returncode:
        return result.returncode
    totals = {k: 0 for k in ("tests", "failures", "errors", "skipped")}
    for suite in ElementTree.parse(report).getroot().iter("testsuite"):
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    if totals["tests"] < 28 or any(totals[k] for k in ("failures", "errors", "skipped")):
        raise RuntimeError("Membership verification incomplete")
    print(f"Membership source scope verified: {totals['tests']} passed, zero skips.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
