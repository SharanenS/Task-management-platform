"""Fail-closed S10 source contracts; no live services, accounts or migrations."""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent


def main():
    report = ROOT / "test-results/reports/s10/source.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/projects/test_owner_decisions.py",
            "tests/projects/test_owner_api.py",
            "tests/projects/test_owner_migration.py",
            "tests/projects/test_review_fallbacks.py",
            "tests/projects/test_owner_cleanup.py",
            "-q",
            "--junitxml",
            str(report),
        ],
        cwd=ROOT,
    )
    if result.returncode:
        return result.returncode
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in ElementTree.parse(report).getroot().iter("testsuite"):
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    if totals["tests"] < 39 or any(totals[key] for key in ("failures", "errors", "skipped")):
        raise RuntimeError("Owner decision source scope incomplete")
    print(f"Owner decision source scope verified: {totals['tests']} passed, zero skips.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
