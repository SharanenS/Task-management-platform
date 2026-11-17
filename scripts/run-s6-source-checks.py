"""Fail-closed calendar source verification with no live services or credentials."""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent


def main():
    report = ROOT / "test-results/reports/s6/source.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/working_calendar", "-q", "--junitxml", str(report)],
        cwd=ROOT,
    )
    if result.returncode:
        return result.returncode
    totals = {k: 0 for k in ("tests", "failures", "errors", "skipped")}
    for suite in ElementTree.parse(report).getroot().iter("testsuite"):
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    if totals["tests"] < 36 or any(totals[k] for k in ("failures", "errors", "skipped")):
        raise RuntimeError("Calendar verification incomplete")
    print(f"Calendar source scope verified: {totals['tests']} passed, zero skips.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
