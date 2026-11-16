"""Fail-closed S2 source verification; no real services, credentials or migrations."""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent


def main():
    report = ROOT / "test-results/reports/s2/backend.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/account_entry", "-q", "--junitxml", str(report)],
        cwd=ROOT,
    )
    if result.returncode:
        return result.returncode
    suites = ElementTree.parse(report).getroot().iter("testsuite")
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    if totals["tests"] < 46 or any(totals[key] for key in ("failures", "errors", "skipped")):
        raise RuntimeError("S2 source verification scope was incomplete")
    print(f"S2 backend source report verified: {totals['tests']} passed, zero skips.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
