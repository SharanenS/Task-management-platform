"""Fail-closed coordination source checks without live services or credentials."""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent


def main():
    report = ROOT / "test-results/reports/s9/coordination.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/projects/test_coordination.py",
            "tests/projects/test_coordination_api.py",
            "tests/projects/test_coordination_migration.py",
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
    if totals["tests"] < 27 or any(totals[k] for k in ("failures", "errors", "skipped")):
        raise RuntimeError("Coordination source verification incomplete")
    print(f"Coordination source scope verified: {totals['tests']} passed, zero skips.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
